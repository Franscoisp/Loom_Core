"""The Meta / Self-Improvement Loop: the learning engine (spec §4.4).

Deterministic and evidence-based. It detects capability gaps and repeated
failures from recorded outcomes, creates *draft* proposals (spec §4.4.5 state
machine), and evaluates them — promoting only when evidence, an expected
improvement, and a concrete success metric are supplied (spec §4.4.4). Every
transition is recorded as an episode for the audit trail.

Task payload shape (``task.kind == "meta"``)::

    {"action": "detect", "min_samples": 3, "low_rate": 0.5}

    {"action": "propose", "proposal_type": "new_skill" | "skill_improvement" |
     "new_tool" | "anti_pattern", ...fields...}

    {"action": "evaluate", "target_id": "...", "decision":
     "promote" | "reject" | "deprecate", "evidence": "...",
     "expected_improvement": "...", "success_metric": "..."}
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast

from loom_core.loops.base import Loop, LoopResult, OwnershipBroker, Task
from loom_core.models import EntryType, Outcome, Status, parse_entry
from loom_core.registry import ToolRecord, ToolRegistry
from loom_core.store import MemoryStore

_STAT_TYPES = {EntryType.skill.value, EntryType.tool.value}
_PROMOTE_EVIDENCE = ("evidence", "expected_improvement", "success_metric")


@dataclass
class Proposal:
    """A detected improvement opportunity (spec §4.4.3)."""

    proposal_type: str
    target_id: str
    rationale: str
    evidence: dict[str, object] = field(default_factory=dict)


class MetaLoop(Loop):
    """Detect gaps, propose skills/tools, and evaluate them (spec §4.4)."""

    name = "meta"

    def __init__(
        self,
        store: MemoryStore,
        broker: OwnershipBroker | None = None,
        registry: ToolRegistry | None = None,
    ) -> None:
        super().__init__(broker=broker)
        self.store = store
        self.registry = registry or ToolRegistry(store.data_dir)

    def can_handle(self, task: Task) -> bool:
        return task.kind == "meta"

    def run(self, task: Task) -> LoopResult:
        action = str(task.payload.get("action", "detect"))
        if action == "detect":
            return self._detect(task)
        if action == "propose":
            return self._propose(task)
        if action == "evaluate":
            return self._evaluate(task)
        return LoopResult(
            status="failure", outcome_summary=f"unknown meta action {action!r}"
        )

    # --- detection (spec §4.4.2) --------------------------------------------

    def detect(self, min_samples: int = 3, low_rate: float = 0.5) -> list[Proposal]:
        proposals: list[Proposal] = []

        # Signal: underperforming skills/tools with enough samples.
        seen: set[str] = set()
        for loaded in self.store.list_entries():
            e = loaded.entry
            if str(e.type) not in _STAT_TYPES or e.id in seen:
                continue
            latest = self.store.latest_version(e.id)
            if latest is None:
                continue
            seen.add(e.id)
            le = latest.entry
            total = int(getattr(le, "success_count", 0)) + int(
                getattr(le, "failure_count", 0)
            )
            rate = float(getattr(le, "success_rate", 0.0))
            if total >= min_samples and rate < low_rate:
                proposals.append(
                    Proposal(
                        proposal_type="skill_improvement",
                        target_id=e.id,
                        rationale=(
                            f"success_rate {rate} over {total} uses is below "
                            f"{low_rate}"
                        ),
                        evidence={"success_rate": rate, "samples": total},
                    )
                )

        # Signal: repeated failures clustered by tag (spec §4.4.2).
        fail_tags: dict[str, list[str]] = defaultdict(list)
        for loaded in self.store.list_entries(type=EntryType.outcome.value):
            if str(loaded.entry.outcome) == Outcome.failure.value:
                for tag in loaded.entry.tags:
                    fail_tags[tag].append(loaded.entry.id)
        for tag, ids in fail_tags.items():
            if len(ids) >= 2:
                proposals.append(
                    Proposal(
                        proposal_type="anti_pattern",
                        target_id=f"repeated-failure-{tag}",
                        rationale=f"{len(ids)} failure outcomes tagged '{tag}'",
                        evidence={"tag": tag, "outcomes": ids},
                    )
                )
        return proposals

    def _detect(self, task: Task) -> LoopResult:
        p = task.payload
        min_samples = int(cast("int", p.get("min_samples", 3)))
        low_rate = float(cast("float", p.get("low_rate", 0.5)))
        proposals = self.detect(min_samples, low_rate)

        session = str(p.get("session_id", datetime.now(UTC).strftime("%Y%m%d-%H%M%S")))
        episode_id = f"meta-detect-{session}"
        body_lines = ["## Meta detection", ""]
        if not proposals:
            body_lines.append("No signals above threshold.")
        for pr in proposals:
            body_lines.append(
                f"- **{pr.proposal_type}** on `{pr.target_id}`: {pr.rationale}"
            )
        episode = parse_entry(
            {
                "id": episode_id,
                "type": "episode",
                "title": f"Meta detection ({len(proposals)} proposal(s))",
                "status": "active",
                "outcome": "success",
                "confidence": 0.7,
                "tags": ["meta", "detection"],
                "source": "meta-loop",
                "provenance": "MetaLoop.detect",
                "session_id": session,
            }
        )
        self.store.write(episode, "\n".join(body_lines))

        return LoopResult(
            status="success",
            outcome_summary=f"Detected {len(proposals)} proposal(s).",
            memory_entries_written=[episode_id],
            metrics={
                "proposals": [
                    {
                        "proposal_type": pr.proposal_type,
                        "target_id": pr.target_id,
                        "rationale": pr.rationale,
                    }
                    for pr in proposals
                ]
            },
        )

    # --- proposal creation (spec §4.4.3, §4.4.6) ----------------------------

    def _propose(self, task: Task) -> LoopResult:
        p = task.payload
        ptype = str(p.get("proposal_type", ""))
        if ptype == "new_skill":
            return self._propose_skill(task, base_id=None)
        if ptype == "skill_improvement":
            base_id = str(p.get("base_id", ""))
            if not base_id:
                return LoopResult(
                    status="failure",
                    outcome_summary="skill_improvement requires 'base_id'",
                )
            return self._propose_skill(task, base_id=base_id)
        if ptype == "new_tool":
            return self._propose_tool(task)
        if ptype == "anti_pattern":
            return self._propose_anti_pattern(task)
        return LoopResult(
            status="failure", outcome_summary=f"unknown proposal_type {ptype!r}"
        )

    def _propose_skill(self, task: Task, base_id: str | None) -> LoopResult:
        p = task.payload
        skill_id = str(p.get("id") or base_id or "")
        if not skill_id:
            return LoopResult(status="failure", outcome_summary="skill needs an 'id'")
        version = self.store.next_version_number(skill_id) if base_id else 1
        related = []
        prev = self.store.latest_version(skill_id) if base_id else None
        if prev is not None:
            related.append(prev.entry.id)
        entry = parse_entry(
            {
                "id": skill_id,
                "type": "skill",
                "title": str(p.get("title", skill_id)),
                "status": "draft",
                "outcome": "unknown",
                "confidence": float(cast("float", p.get("confidence", 0.5))),
                "tags": cast("list[str]", p.get("tags", [])) or ["proposed"],
                "related": related,
                "source": "meta-loop",
                "provenance": str(p.get("rationale", "Proposed by MetaLoop.")),
                "version": version,
                "inputs": str(p.get("inputs", "")),
                "outputs": str(p.get("outputs", "")),
                "steps": str(p.get("steps", "")),
            }
        )
        self.store.write(entry, str(p.get("body", "")))
        self._audit("propose", entry.id, f"draft skill v{version}")
        return LoopResult(
            status="success",
            outcome_summary=f"Proposed draft skill {skill_id!r} v{version}.",
            memory_entries_written=[entry.id],
            metrics={"proposal_type": "skill", "version": version},
        )

    def _propose_tool(self, task: Task) -> LoopResult:
        p = task.payload
        tool_id = str(p.get("id", ""))
        if not tool_id:
            return LoopResult(status="failure", outcome_summary="tool needs an 'id'")
        version = self.store.next_version_number(tool_id)
        tool = parse_entry(
            {
                "id": tool_id,
                "type": "tool",
                "title": str(p.get("title", tool_id)),
                "status": "draft",
                "outcome": "unknown",
                "confidence": float(cast("float", p.get("confidence", 0.5))),
                "tags": cast("list[str]", p.get("tags", [])) or ["proposed", "tool"],
                "source": "meta-loop",
                "provenance": "Tool proposed by MetaLoop (candidate).",
                "version": version,
                "inputs": str(p.get("inputs", "")),
                "outputs": str(p.get("outputs", "")),
                "steps": str(p.get("steps", "")),
            }
        )
        self.store.write(tool, str(p.get("spec", "")))

        # An initial skill that knows how to use the tool (spec §4.4.6 step 4).
        skill_id = str(p.get("skill_id", f"use-{tool_id}"))
        skill = parse_entry(
            {
                "id": skill_id,
                "type": "skill",
                "title": f"Use the {tool_id} tool",
                "status": "draft",
                "outcome": "unknown",
                "confidence": 0.5,
                "tags": ["proposed", "tool-usage"],
                "related": [tool_id],
                "source": "meta-loop",
                "provenance": f"Companion skill for tool {tool_id}.",
                "version": 1,
                "steps": str(p.get("steps", "")),
            }
        )
        self.store.write(skill, f"How to invoke `{tool_id}`.")

        # Register as a candidate (spec §5.4, §4.4.6 step 5).
        self.registry.register(
            ToolRecord(
                id=tool_id,
                version=version,
                status="candidate",
                skill_id=skill_id,
                spec=str(p.get("spec", "")),
            )
        )
        self._audit("propose", tool_id, f"candidate tool v{version} + skill {skill_id}")
        return LoopResult(
            status="success",
            outcome_summary=(
                f"Proposed candidate tool {tool_id!r} v{version} and companion "
                f"skill {skill_id!r}."
            ),
            memory_entries_written=[tool_id, skill_id],
            artifacts=[str(self.registry.path)],
            metrics={"proposal_type": "tool", "version": version},
        )

    def _propose_anti_pattern(self, task: Task) -> LoopResult:
        p = task.payload
        ap_id = str(p.get("id", ""))
        if not ap_id:
            return LoopResult(
                status="failure", outcome_summary="anti_pattern needs an 'id'"
            )
        entry = parse_entry(
            {
                "id": ap_id,
                "type": "anti-pattern",
                "title": str(p.get("title", ap_id)),
                "status": "draft",
                "outcome": "failure",
                "confidence": float(cast("float", p.get("confidence", 0.6))),
                "tags": cast("list[str]", p.get("tags", [])) or ["anti-pattern"],
                "source": "meta-loop",
                "provenance": str(p.get("rationale", "Proposed by MetaLoop.")),
            }
        )
        self.store.write(entry, str(p.get("body", "")))
        self._audit("propose", ap_id, "draft anti-pattern")
        return LoopResult(
            status="success",
            outcome_summary=f"Proposed draft anti-pattern {ap_id!r}.",
            memory_entries_written=[ap_id],
            metrics={"proposal_type": "anti_pattern"},
        )

    # --- evaluation (spec §4.4.4, §4.4.5) -----------------------------------

    def _evaluate(self, task: Task) -> LoopResult:
        p = task.payload
        target_id = str(p.get("target_id", ""))
        decision = str(p.get("decision", ""))
        loaded = self.store.latest_version(target_id) or self.store.get(target_id)
        if loaded is None:
            return LoopResult(
                status="failure", outcome_summary=f"no entry with id {target_id!r}"
            )

        if decision == "promote":
            missing = [k for k in _PROMOTE_EVIDENCE if not str(p.get(k, "")).strip()]
            if missing:
                self._audit("evaluate", target_id, f"promotion blocked: missing {missing}")
                return LoopResult(
                    status="partial",
                    outcome_summary=(
                        f"Promotion of {target_id!r} blocked; insufficient "
                        f"evidence (missing: {', '.join(missing)})."
                    ),
                    metrics={"decision": "blocked", "missing": missing},
                )
            new_status = Status.promoted.value
        elif decision == "reject":
            new_status = Status.rejected.value
        elif decision == "deprecate":
            new_status = Status.deprecated.value
        else:
            return LoopResult(
                status="failure", outcome_summary=f"unknown decision {decision!r}"
            )

        entry = loaded.entry
        entry.status = new_status  # type: ignore[assignment]
        entry.updated = datetime.now(UTC)
        self.store.write(entry, loaded.body)

        if str(entry.type) == EntryType.tool.value:
            reg_status = "promoted" if new_status == Status.promoted.value else new_status
            self.registry.set_status(target_id, reg_status)

        self._audit(
            "evaluate",
            target_id,
            f"{decision} -> {new_status}",
            evidence={k: p.get(k) for k in _PROMOTE_EVIDENCE if p.get(k)},
        )
        return LoopResult(
            status="success",
            outcome_summary=f"{decision.title()}d {target_id!r} (status={new_status}).",
            memory_entries_written=[target_id],
            metrics={"decision": decision, "status": new_status},
        )

    # --- audit trail --------------------------------------------------------

    def _audit(
        self,
        action: str,
        target_id: str,
        note: str,
        evidence: dict[str, object] | None = None,
    ) -> None:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
        episode_id = f"meta-{action}-{target_id}-{stamp}"
        body = [f"## Meta {action}", "", f"- target: `{target_id}`", f"- {note}"]
        if evidence:
            body.append("")
            body.append("### Evidence")
            for k, v in evidence.items():
                body.append(f"- {k}: {v}")
        episode = parse_entry(
            {
                "id": episode_id,
                "type": "episode",
                "title": f"Meta {action}: {target_id}",
                "status": "active",
                "outcome": "success",
                "confidence": 0.8,
                "tags": ["meta", "audit", action],
                "source": "meta-loop",
                "provenance": "MetaLoop audit trail (spec §4.4.1).",
                "session_id": f"meta-{stamp}",
            }
        )
        self.store.write(episode, "\n".join(body))
