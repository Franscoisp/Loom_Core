import pytest

from loom_core.loops.base import Loop, LoopResult, Task
from loom_core.orchestrator import Orchestrator, OwnershipError
from loom_core.store import MemoryStore


class DummyLoop(Loop):
    name = "dummy"

    def __init__(self, kind: str = "dummy") -> None:
        super().__init__()
        self._kind = kind
        self.ran: list[str] = []

    def can_handle(self, task: Task) -> bool:
        return task.kind == self._kind

    def run(self, task: Task) -> LoopResult:
        self.ran.append(task.id)
        return LoopResult(status="success", outcome_summary=f"ran {task.id}")


def test_loop_result_rejects_bad_status() -> None:
    with pytest.raises(ValueError):
        LoopResult(status="ok", outcome_summary="x")


def test_grant_and_revoke(tmp_path) -> None:
    orch = Orchestrator(MemoryStore(tmp_path / "data"))
    assert orch.grant("t1", "a") is True
    assert orch.owner_of("t1") == "a"
    assert orch.grant("t1", "b") is False  # already owned by a
    assert orch.grant("t1", "a") is True  # idempotent for same owner
    with pytest.raises(OwnershipError):
        orch.revoke("t1", "b")
    orch.revoke("t1", "a")
    assert orch.owner_of("t1") is None


def test_dispatch_claims_and_releases(tmp_path) -> None:
    orch = Orchestrator(MemoryStore(tmp_path / "data"))
    loop = DummyLoop()
    orch.register(loop)
    result = orch.dispatch(Task(id="t1", kind="dummy"))
    assert result.status == "success"
    assert loop.ran == ["t1"]
    # released after run
    assert orch.owner_of("t1") is None


def test_dispatch_no_loop_raises(tmp_path) -> None:
    orch = Orchestrator(MemoryStore(tmp_path / "data"))
    with pytest.raises(OwnershipError):
        orch.dispatch(Task(id="t1", kind="unknown"))


def test_claim_requires_broker() -> None:
    loop = DummyLoop()
    with pytest.raises(RuntimeError):
        loop.claim("t1")
