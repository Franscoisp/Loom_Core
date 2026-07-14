"""The Distillation Loop: raw session activity -> structured memory (spec §4.2).

This MVP is deterministic and does not invent facts (spec §4.2 quality rules):
it consumes explicit candidate entries and skill-usage outcomes from the task
payload, validates and writes them, updates skill statistics, and records an
episode noting that distillation occurred.

Task payload shape (``task.kind == "distill"``)::

    {
      "session_id": "2026-07-14-03",
      "candidates": [ {<entry frontmatter>, "body": "..."} , ... ],
      "skills_used": [ {"id": "run-quality-gates", "outcome": "success"}, ... ],
      "summary": "free-text summary of the session",
      "related_tasks": ["TASK-023"],
    }
"""

from __future__ import annotations

from typing import cast

from loom_core.loops.base import Loop, LoopResult, OwnershipBroker, Task
from loom_core.models import parse_entry
from loom_core.store import MemoryStore


class DistillationLoop(Loop):
    """Turn a session's raw activity into clean Loom Memory entries."""

    name = "distillation"

    def __init__(
        self, store: MemoryStore, broker: OwnershipBroker | None = None
    ) -> None:
        super().__init__(broker=broker)
        self.store = store

    def can_handle(self, task: Task) -> bool:
        return task.kind == "distill"

    def run(self, task: Task) -> LoopResult:
        payload = task.payload
        session_id = str(payload.get("session_id") or task.id)
        candidates = cast("list[dict[str, object]]", payload.get("candidates", []))
        skills_used = cast("list[dict[str, object]]", payload.get("skills_used", []))
        summary = str(payload.get("summary", ""))
        related_tasks = cast("list[str]", payload.get("related_tasks", []))

        written: list[str] = []
        drafted = 0

        # 1-4: write well-formed memory entries for each candidate.
        for cand in candidates:
            data = {k: v for k, v in cand.items() if k != "body"}
            body = str(cand.get("body", ""))
            entry = parse_entry(data)
            if str(entry.status) == "draft":
                drafted += 1
            self.store.write(entry, body)
            written.append(entry.id)

        # 5: update success/failure counts on skills/tools that were used.
        stats_updated: list[str] = []
        for used in skills_used:
            sid = str(used.get("id", ""))
            outcome = str(used.get("outcome", "unknown"))
            if sid and self.store.update_stats(sid, outcome):
                stats_updated.append(sid)

        # 6: record an episode that distillation itself occurred.
        episode_id = f"distill-{session_id}"
        episode_body = self._episode_body(
            summary, written, stats_updated, drafted
        )
        episode = parse_entry(
            {
                "id": episode_id,
                "type": "episode",
                "title": f"Distillation of session {session_id}",
                "status": "active",
                "outcome": "success",
                "confidence": 0.8,
                "tags": ["distillation", "session"],
                "source": "distillation",
                "provenance": f"DistillationLoop run for session {session_id}",
                "session_id": session_id,
                "related_tasks": related_tasks,
            }
        )
        self.store.write(episode, episode_body)
        written.append(episode.id)

        return LoopResult(
            status="success",
            outcome_summary=(
                f"Distilled {len(candidates)} candidate(s) into memory; "
                f"updated stats for {len(stats_updated)} skill/tool(s)."
            ),
            memory_entries_written=written,
            lessons=summary,
            metrics={
                "candidates_written": len(candidates),
                "drafted": drafted,
                "stats_updated": len(stats_updated),
            },
        )

    # --- helpers ------------------------------------------------------------

    @staticmethod
    def _episode_body(
        summary: str, written: list[str], stats_updated: list[str], drafted: int
    ) -> str:
        lines = ["## Distillation summary", ""]
        if summary:
            lines += [summary, ""]
        lines.append("## Entries written")
        lines += [f"- {wid}" for wid in written] or ["- (none)"]
        if stats_updated:
            lines += ["", "## Skill/tool stats updated"]
            lines += [f"- {sid}" for sid in stats_updated]
        if drafted:
            lines += ["", f"_{drafted} entr(y/ies) written as draft (low confidence)._"]
        return "\n".join(lines)
