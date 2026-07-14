from pathlib import Path

import pytest

from loom_core.loops.base import Task
from loom_core.loops.distillation import DistillationLoop
from loom_core.orchestrator import Orchestrator
from loom_core.store import MemoryStore


@pytest.fixture()
def orch(tmp_path: Path) -> Orchestrator:
    store = MemoryStore(tmp_path / "data")
    o = Orchestrator(store)
    o.register(DistillationLoop(store))
    return o


def test_dispatch_is_logged(orch: Orchestrator) -> None:
    orch.dispatch(
        Task(
            id="s1",
            kind="distill",
            payload={"session_id": "s1", "candidates": []},
        )
    )
    log = orch.dispatch_log()
    assert len(log) == 1
    rec = log[0]
    assert rec["loop"] == "distillation"
    assert rec["task_kind"] == "distill"
    assert rec["status"] == "success"
    assert rec["wrote_memory"] is True


def test_distillation_run_increments_metric(orch: Orchestrator) -> None:
    orch.dispatch(
        Task(id="s1", kind="distill", payload={"session_id": "s1", "candidates": []})
    )
    assert orch.metrics.load().distillation_runs == 1


def test_ownership_conflict_metric(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "data")
    orch = Orchestrator(store)
    orch.grant("t1", "loopA")
    assert orch.grant("t1", "loopB") is False
    assert orch.metrics.load().ownership_conflicts == 1
