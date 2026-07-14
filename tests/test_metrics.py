from pathlib import Path

import pytest

from loom_core.metrics import MetricsStore, compute_metrics
from loom_core.models import parse_entry
from loom_core.store import MemoryStore


@pytest.fixture()
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(tmp_path / "data")


def test_counters_persist_and_increment(store: MemoryStore) -> None:
    ms = MetricsStore(store.data_dir)
    assert ms.load().distillation_runs == 0
    ms.increment("distillation_runs")
    ms.increment("distillation_runs")
    assert MetricsStore(store.data_dir).load().distillation_runs == 2


def test_increment_unknown_counter_raises(store: MemoryStore) -> None:
    with pytest.raises(ValueError):
        MetricsStore(store.data_dir).increment("nope")


def test_compute_metrics_from_memory(store: MemoryStore) -> None:
    store.write(
        parse_entry(
            {
                "id": "d1",
                "type": "core",
                "title": "Decision",
                "source": "user",
                "status": "active",
            }
        )
    )
    store.write(
        parse_entry(
            {
                "id": "sk",
                "type": "skill",
                "title": "Skill v1",
                "source": "meta-loop",
                "status": "draft",
                "version": 1,
                "success_count": 3,
                "failure_count": 1,
            }
        )
    )
    store.write(
        parse_entry(
            {
                "id": "sk",
                "type": "skill",
                "title": "Skill v2",
                "source": "meta-loop",
                "status": "promoted",
                "version": 2,
                "success_count": 5,
                "failure_count": 0,
            }
        )
    )

    m = compute_metrics(store)
    assert m["decisions_preserved"] == 1
    assert m["skills_created"] == 1  # distinct id
    assert m["skills_improved"] == 1  # two versions of "sk"
    assert m["skills_promoted"] == 1  # latest version is promoted
    assert m["average_skill_success_rate"] == 1.0  # latest v2 rate


def test_compute_metrics_empty(store: MemoryStore) -> None:
    m = compute_metrics(store)
    assert m["skills_created"] == 0
    assert m["average_skill_success_rate"] == 0.0
