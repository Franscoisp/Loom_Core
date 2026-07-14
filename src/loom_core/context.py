"""Context packing: selective retrieval within a token budget (spec §3.5).

The packer ranks candidate memory entries by the spec's signals (tag/project
match, skill success rate, recency, confidence), then greedily fills a token
budget. It records *why* each entry was included so value metrics (spec §8) and
debugging are possible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from loom_core.models import BaseEntry, EntryType, Status
from loom_core.store import LoadedEntry, MemoryStore


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token). Deterministic and cheap."""
    return max(1, len(text) // 4)


@dataclass
class PackItem:
    entry: BaseEntry
    tokens: int
    score: float
    reasons: list[str]
    text: str


@dataclass
class ContextPack:
    query: str
    token_budget: int
    tokens_used: int = 0
    tokens_saved_estimate: int = 0
    items: list[PackItem] = field(default_factory=list)

    def render(self) -> str:
        """Render the pack as a single string suitable for a model prompt."""
        blocks = [item.text for item in self.items]
        return "\n\n---\n\n".join(blocks)


@runtime_checkable
class ContextProvider(Protocol):
    """What a loop needs to request an optimized context pack (spec §6).

    The Orchestrator implements this; loops depend on the protocol so context
    assembly always flows through the single arbiter.
    """

    def context_pack(
        self,
        query: str = "",
        *,
        tags: list[str] | None = None,
        project: str | None = None,
        token_budget: int = 2000,
    ) -> ContextPack: ...


def _as_str(type_or_status: object) -> str:
    return str(type_or_status)


def _recency_score(updated: datetime) -> float:
    now = datetime.now(UTC)
    ref = updated if updated.tzinfo is not None else updated.replace(tzinfo=UTC)
    age_days = max(0.0, (now - ref).total_seconds() / 86400.0)
    return 1.0 / (1.0 + age_days)


class ContextPacker:
    """Assemble optimized context packs from the memory store (spec §3.5)."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def _score(
        self,
        loaded: LoadedEntry,
        query_tags: set[str],
        project: str | None,
    ) -> tuple[float, list[str]]:
        e = loaded.entry
        reasons: list[str] = []
        score = 0.0

        entry_tags = {t.lower() for t in e.tags}
        matched = query_tags & entry_tags
        if matched:
            score += 10.0 * len(matched)
            reasons.append(f"tag match: {', '.join(sorted(matched))}")

        if project and project.lower() in entry_tags:
            score += 8.0
            reasons.append(f"project match: {project}")

        etype = _as_str(e.type)

        # Active Core entries are almost always relevant (spec §3.2.1 / §3.5).
        if etype in (EntryType.core.value, EntryType.preference.value):
            score += 4.0
            reasons.append("core/preference layer")
            if _as_str(e.status) in (Status.active.value, Status.promoted.value):
                score += 2.0
                reasons.append("active/promoted")

        # Prefer high-success, recently used skills/tools (spec §3.5).
        if etype in (EntryType.skill.value, EntryType.tool.value):
            rate = float(getattr(e, "success_rate", 0.0))
            score += 5.0 * rate
            if rate:
                reasons.append(f"success_rate={rate}")
            if _as_str(e.status) in (Status.promoted.value, Status.active.value):
                score += 1.0

        recency = _recency_score(e.updated)
        score += 3.0 * recency
        score += 2.0 * float(e.confidence)
        reasons.append(f"recency={recency:.2f}")
        reasons.append(f"confidence={e.confidence}")
        return score, reasons

    def pack(
        self,
        query: str = "",
        *,
        tags: list[str] | None = None,
        project: str | None = None,
        token_budget: int = 2000,
        exclude_deprecated: bool = True,
    ) -> ContextPack:
        """Build a context pack respecting the token budget strictly."""
        query_tags = {t.lower() for t in (tags or [])}
        if query:
            query_tags |= {w.lower() for w in query.split()}

        candidates: list[tuple[float, list[str], LoadedEntry, int, str]] = []
        total_candidate_tokens = 0

        for loaded in self.store.list_entries():
            e = loaded.entry
            if exclude_deprecated and _as_str(e.status) == Status.deprecated.value:
                continue
            text = self._render_entry(loaded)
            tokens = estimate_tokens(text)
            total_candidate_tokens += tokens
            score, reasons = self._score(loaded, query_tags, project)
            candidates.append((score, reasons, loaded, tokens, text))

        candidates.sort(key=lambda c: (-c[0], -_recency_score(c[2].entry.updated)))

        pack = ContextPack(query=query, token_budget=token_budget)
        used = 0
        for score, reasons, loaded, tokens, text in candidates:
            if score <= 0:
                continue
            if used + tokens > token_budget:
                continue
            used += tokens
            pack.items.append(
                PackItem(
                    entry=loaded.entry,
                    tokens=tokens,
                    score=round(score, 4),
                    reasons=reasons,
                    text=text,
                )
            )

        pack.tokens_used = used
        pack.tokens_saved_estimate = max(0, total_candidate_tokens - used)
        return pack

    @staticmethod
    def _render_entry(loaded: LoadedEntry) -> str:
        e = loaded.entry
        header = f"[{_as_str(e.type)}] {e.title} (id={e.id})"
        body = loaded.body.strip()
        return f"{header}\n{body}" if body else header
