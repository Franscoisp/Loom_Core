from pathlib import Path

import pytest

from loom_core.loops.base import Task
from loom_core.loops.distillation import DistillationLoop
from loom_core.models import parse_entry
from loom_core.orchestrator import Orchestrator
from loom_core.store import MemoryStore


@pytest.fixture()
def orch(tmp_path: Path) -> Orchestrator:
    store = MemoryStore(tmp_path / "data")
    o = Orchestrator(store)
    o.register(DistillationLoop(store))
    return o


def test_distillation_writes_candidates_and_episode(orch: Orchestrator) -> None:
    task = Task(
        id="2026-07-14-99",
        kind="distill",
        payload={
            "session_id": "2026-07-14-99",
            "summary": "Did a thing.",
            "related_tasks": ["TASK-023"],
            "candidates": [
                {
                    "id": "decision-x",
                    "type": "core",
                    "title": "We chose X",
                    "source": "distillation",
                    "status": "active",
                    "body": "Because Y.",
                }
            ],
        },
    )
    result = orch.dispatch(task)
    assert result.status == "success"
    assert "decision-x" in result.memory_entries_written
    assert "distill-2026-07-14-99" in result.memory_entries_written

    assert orch.store.get("decision-x") is not None
    episode = orch.store.get("distill-2026-07-14-99")
    assert episode is not None
    assert "decision-x" in episode.body


def test_distillation_updates_skill_stats(orch: Orchestrator) -> None:
    orch.store.write(
        parse_entry(
            {
                "id": "make-tea",
                "type": "skill",
                "title": "Make tea",
                "source": "meta-loop",
                "success_count": 2,
                "failure_count": 0,
            }
        ),
        "steps",
    )
    task = Task(
        id="s1",
        kind="distill",
        payload={
            "session_id": "s1",
            "candidates": [],
            "skills_used": [
                {"id": "make-tea", "outcome": "success"},
                {"id": "make-tea", "outcome": "failure"},
            ],
        },
    )
    result = orch.dispatch(task)
    assert result.metrics["stats_updated"] == 2

    updated = orch.store.get("make-tea")
    assert updated is not None
    assert updated.entry.success_count == 3  # type: ignore[attr-defined]
    assert updated.entry.failure_count == 1  # type: ignore[attr-defined]
    assert updated.entry.success_rate == 0.75  # type: ignore[attr-defined]


def test_distillation_can_handle() -> None:
    from loom_core.store import MemoryStore

    loop = DistillationLoop(MemoryStore())
    assert loop.can_handle(Task(id="x", kind="distill")) is True
    assert loop.can_handle(Task(id="x", kind="other")) is False
