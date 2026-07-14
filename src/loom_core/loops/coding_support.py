"""The Coding Support Loop: help OpenCode do better work (spec §4.3).

Responsibilities:

- Before major coding steps, request an optimized context pack from the
  Orchestrator (never assemble packs itself — spec §6).
- Surface relevant existing skills so good procedures get reused.
- After coding attempts (tests, user feedback), record the outcome and update
  the statistics of any skills that were used.

It never takes ownership of code-writing; it only supplies context and records
outcomes.

Task payload shape (``task.kind == "coding_support"``)::

    {"action": "context", "query": "...", "tags": [...], "project": "...",
     "token_budget": 2000}

    {"action": "surface_skills", "query": "...", "limit": 5}

    {"action": "record_outcome", "id": "...", "title": "...", "outcome":
     "success|failure|partial", "summary": "...", "tags": [...],
     "related_tasks": [...], "confidence": 0.8,
     "skills_used": [{"id": "...", "outcome": "success"}]}
"""

from __future__ import annotations

from typing import cast

from loom_core.context import ContextProvider
from loom_core.loops.base import Loop, LoopResult, OwnershipBroker, Task
from loom_core.models import EntryType, parse_entry
from loom_core.store import MemoryStore


class CodingSupportLoop(Loop):
    """Supply high-quality context and record coding outcomes (spec §4.3)."""

    name = "coding-support"

    def __init__(
        self,
        store: MemoryStore,
        context_provider: ContextProvider,
        broker: OwnershipBroker | None = None,
    ) -> None:
        super().__init__(broker=broker)
        self.store = store
        self.context_provider = context_provider

    def can_handle(self, task: Task) -> bool:
        return task.kind == "coding_support"

    def run(self, task: Task) -> LoopResult:
        action = str(task.payload.get("action", "context"))
        if action == "context":
            return self._context(task)
        if action == "surface_skills":
            return self._surface_skills(task)
        if action == "record_outcome":
            return self._record_outcome(task)
        return LoopResult(
            status="failure",
            outcome_summary=f"unknown coding_support action {action!r}",
        )

    # --- actions ------------------------------------------------------------

    def _context(self, task: Task) -> LoopResult:
        p = task.payload
        query = str(p.get("query", ""))
        tags = cast("list[str] | None", p.get("tags"))
        project = cast("str | None", p.get("project"))
        budget = int(cast("int", p.get("token_budget", 2000)))
        pack = self.context_provider.context_pack(
            query, tags=tags, project=project, token_budget=budget
        )
        return LoopResult(
            status="success",
            outcome_summary=(
                f"Assembled context pack: {len(pack.items)} item(s), "
                f"{pack.tokens_used}/{pack.token_budget} tokens."
            ),
            artifacts=[i.entry.id for i in pack.items],
            metrics={
                "tokens_used": pack.tokens_used,
                "tokens_saved_estimate": pack.tokens_saved_estimate,
                "items": [i.entry.id for i in pack.items],
                "rendered": pack.render(),
            },
        )

    def _surface_skills(self, task: Task) -> LoopResult:
        p = task.payload
        query = str(p.get("query", ""))
        limit = int(cast("int", p.get("limit", 5)))
        hits = [
            loaded
            for loaded in self.store.search(query)
            if str(loaded.entry.type) in (EntryType.skill.value, EntryType.tool.value)
        ][:limit]
        ids = [loaded.entry.id for loaded in hits]
        return LoopResult(
            status="success",
            outcome_summary=(
                f"Surfaced {len(ids)} relevant skill/tool(s) for {query!r}."
            ),
            artifacts=ids,
            metrics={"skills": ids},
        )

    def _record_outcome(self, task: Task) -> LoopResult:
        p = task.payload
        outcome = str(p.get("outcome", "unknown"))
        entry_id = str(p.get("id", f"outcome-{task.id}"))
        entry = parse_entry(
            {
                "id": entry_id,
                "type": "outcome",
                "title": str(p.get("title", f"Outcome for {task.id}")),
                "status": "active",
                "outcome": outcome,
                "confidence": float(cast("float", p.get("confidence", 0.7))),
                "tags": cast("list[str]", p.get("tags", [])) or ["coding"],
                "related": cast("list[str]", p.get("related", [])),
                "source": "coding-loop",
                "provenance": f"Recorded by CodingSupportLoop for task {task.id}.",
            }
        )
        self.store.write(entry, str(p.get("summary", "")))
        written = [entry.id]

        stats_updated: list[str] = []
        for used in cast("list[dict[str, object]]", p.get("skills_used", [])):
            sid = str(used.get("id", ""))
            oc = str(used.get("outcome", outcome))
            if sid and self.store.update_stats(sid, oc):
                stats_updated.append(sid)

        return LoopResult(
            status="success" if outcome != "failure" else "partial",
            outcome_summary=(
                f"Recorded {outcome} outcome {entry_id!r}; updated "
                f"{len(stats_updated)} skill/tool stat(s)."
            ),
            memory_entries_written=written,
            metrics={"outcome": outcome, "stats_updated": stats_updated},
        )
