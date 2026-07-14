"""Value metrics (spec §8), derived from real recorded data.

Some metrics are computed directly from the memory store (decisions preserved,
skill counts, average success rate); others are cumulative event counters that
only make sense over time (distillation runs, recovery events, ownership
conflicts, tokens saved) and are persisted to ``data/metrics.json``.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass

from loom_core.locking import FileLock
from loom_core.models import BaseEntry, EntryType, Status
from loom_core.store import MemoryStore

METRICS_FILENAME = "metrics.json"


@dataclass
class MetricsCounters:
    """Cumulative, event-driven counters (spec §8)."""

    distillation_runs: int = 0
    recovery_events: int = 0
    ownership_conflicts: int = 0
    skills_promoted_events: int = 0
    tokens_saved_cumulative: int = 0


class MetricsStore:
    """Persist and increment cumulative metric counters."""

    def __init__(self, data_dir: str | os.PathLike[str] | None = None) -> None:
        store = MemoryStore(data_dir)
        self.data_dir = store.data_dir
        self.path = self.data_dir / METRICS_FILENAME

    def load(self) -> MetricsCounters:
        if not self.path.exists():
            return MetricsCounters()
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        known = {f: raw[f] for f in MetricsCounters().__dict__ if f in raw}
        return MetricsCounters(**known)

    def save(self, counters: MetricsCounters) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(asdict(counters), fh, indent=2, sort_keys=True)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    def increment(self, field: str, by: int = 1) -> MetricsCounters:
        if field not in MetricsCounters().__dict__:
            raise ValueError(f"unknown counter {field!r}")
        with FileLock(self.path):
            counters = self.load()
            setattr(counters, field, getattr(counters, field) + by)
            self.save(counters)
        return counters


def _latest_skill_versions(store: MemoryStore) -> dict[str, BaseEntry]:
    """Map each skill id -> its highest-version entry."""
    latest: dict[str, BaseEntry] = {}
    best_version: dict[str, int] = {}
    for loaded in store.list_entries(type=EntryType.skill.value):
        e = loaded.entry
        v = int(getattr(e, "version", 1))
        if e.id not in best_version or v > best_version[e.id]:
            best_version[e.id] = v
            latest[e.id] = e
    return latest


def compute_metrics(
    store: MemoryStore, counters: MetricsCounters | None = None
) -> dict[str, object]:
    """Derive the spec §8 metrics from memory plus cumulative counters."""
    counters = counters or MetricsStore(store.data_dir).load()

    entries = store.list_entries()

    decisions_preserved = sum(
        1
        for lo in entries
        if str(lo.entry.type) in (EntryType.core.value, EntryType.preference.value)
        and str(lo.entry.status) in (Status.active.value, Status.promoted.value)
    )

    latest_skills = _latest_skill_versions(store)
    skills_created = len(latest_skills)
    skills_promoted = sum(
        1 for e in latest_skills.values() if str(e.status) == Status.promoted.value
    )

    version_counts: dict[str, int] = {}
    for lo in entries:
        if str(lo.entry.type) == EntryType.skill.value:
            version_counts[lo.entry.id] = version_counts.get(lo.entry.id, 0) + 1
    skills_improved = sum(1 for c in version_counts.values() if c > 1)

    rates = [float(getattr(e, "success_rate", 0.0)) for e in latest_skills.values()]
    average_skill_success_rate = round(sum(rates) / len(rates), 4) if rates else 0.0

    return {
        "tokens_saved_estimate": counters.tokens_saved_cumulative,
        "decisions_preserved": decisions_preserved,
        "skills_created": skills_created,
        "skills_promoted": skills_promoted,
        "skills_improved": skills_improved,
        "average_skill_success_rate": average_skill_success_rate,
        "distillation_runs": counters.distillation_runs,
        "recovery_events": counters.recovery_events,
        "ownership_conflicts": counters.ownership_conflicts,
    }
