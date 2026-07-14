from pathlib import Path

import pytest

from loom_core.registry import ToolRecord, ToolRegistry
from loom_core.store import MemoryStore
from loom_core.tooling import (
    ToolExecutor,
    ToolNotAllowedError,
    ToolNotFoundError,
    build_default_executor,
)


@pytest.fixture()
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(tmp_path / "data")


def test_candidate_tool_is_gated(store: MemoryStore) -> None:
    ex = ToolExecutor(store)
    ex.register("echo", lambda p: {"echoed": p})
    with pytest.raises(ToolNotAllowedError):
        ex.run("echo", {"x": 1})
    run = ex.run("echo", {"x": 1}, allow_candidate=True)
    assert run.ok is True
    assert run.output == {"echoed": {"x": 1}}


def test_unknown_tool_raises(store: MemoryStore) -> None:
    with pytest.raises(ToolNotFoundError):
        ToolExecutor(store).run("missing", {})


def test_promoted_tool_runs_freely(store: MemoryStore) -> None:
    reg = ToolRegistry(store.data_dir)
    reg.register(ToolRecord(id="t", version=1, status="promoted"))
    ex = ToolExecutor(store, registry=reg)
    ex.register("t", lambda p: {"ok": True}, auto_register=False)
    run = ex.run("t", {})
    assert run.ok is True


def test_run_records_outcome_and_stats(store: MemoryStore) -> None:
    reg = ToolRegistry(store.data_dir)
    reg.register(ToolRecord(id="t", version=1, status="promoted"))
    ex = ToolExecutor(store, registry=reg)
    ex.register("t", lambda p: {"ok": True}, auto_register=False)
    run = ex.run("t", {})
    assert store.get(run.outcome_entry_id) is not None


def test_failure_is_recorded_not_raised(store: MemoryStore) -> None:
    ex = ToolExecutor(store)

    def boom(_p: dict) -> dict:
        raise RuntimeError("kaboom")

    ex.register("boom", boom)
    run = ex.run("boom", {}, allow_candidate=True)
    assert run.ok is False
    assert "kaboom" in str(run.output["error"])


def test_builtin_frontmatter_linter(store: MemoryStore) -> None:
    from loom_core.models import parse_entry

    store.write(
        parse_entry({"id": "ok1", "type": "core", "title": "T", "source": "user"})
    )
    ex = build_default_executor(store)
    run = ex.run("frontmatter-linter", {}, allow_candidate=True)
    assert run.output["ok"] is True
    assert run.output["checked"] >= 1


def test_builtin_memory_summary(store: MemoryStore) -> None:
    from loom_core.models import parse_entry

    store.write(
        parse_entry({"id": "c", "type": "core", "title": "T", "source": "user"})
    )
    ex = build_default_executor(store)
    run = ex.run("memory-summary", {}, allow_candidate=True)
    assert run.output["total"] >= 1
