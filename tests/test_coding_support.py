from pathlib import Path

import pytest

from loom_core.loops.base import Task
from loom_core.loops.coding_support import CodingSupportLoop
from loom_core.models import parse_entry
from loom_core.orchestrator import Orchestrator
from loom_core.store import MemoryStore


@pytest.fixture()
def setup(tmp_path: Path) -> tuple[Orchestrator, CodingSupportLoop, MemoryStore]:
    store = MemoryStore(tmp_path / "data")
    orch = Orchestrator(store)
    loop = CodingSupportLoop(store, context_provider=orch)
    orch.register(loop)
    return orch, loop, store


def test_context_action_requests_pack(setup) -> None:
    orch, _loop, store = setup
    store.write(
        parse_entry(
            {
                "id": "c1",
                "type": "core",
                "title": "Loom fact",
                "source": "user",
                "status": "active",
                "tags": ["loom"],
            }
        ),
        "body",
    )
    result = orch.dispatch(
        Task(id="t", kind="coding_support", payload={"action": "context", "tags": ["loom"]})
    )
    assert result.status == "success"
    assert "c1" in result.artifacts
    assert "rendered" in result.metrics


def test_surface_skills(setup) -> None:
    orch, _loop, store = setup
    store.write(
        parse_entry(
            {
                "id": "deploy-thing",
                "type": "skill",
                "title": "Deploy the thing",
                "source": "meta-loop",
                "tags": ["deploy"],
            }
        ),
        "deploy steps",
    )
    result = orch.dispatch(
        Task(
            id="t",
            kind="coding_support",
            payload={"action": "surface_skills", "query": "deploy"},
        )
    )
    assert "deploy-thing" in result.metrics["skills"]


def test_record_outcome_writes_and_updates_stats(setup) -> None:
    orch, _loop, store = setup
    store.write(
        parse_entry(
            {
                "id": "build-skill",
                "type": "skill",
                "title": "Build",
                "source": "meta-loop",
                "success_count": 1,
                "failure_count": 0,
            }
        ),
        "steps",
    )
    result = orch.dispatch(
        Task(
            id="t42",
            kind="coding_support",
            payload={
                "action": "record_outcome",
                "id": "outcome-t42",
                "title": "Build passed",
                "outcome": "success",
                "summary": "All green.",
                "skills_used": [{"id": "build-skill", "outcome": "success"}],
            },
        )
    )
    assert result.status == "success"
    assert store.get("outcome-t42") is not None
    updated = store.get("build-skill")
    assert updated is not None
    assert updated.entry.success_count == 2  # type: ignore[attr-defined]


def test_unknown_action_fails(setup) -> None:
    orch, _loop, _store = setup
    result = orch.dispatch(
        Task(id="t", kind="coding_support", payload={"action": "nope"})
    )
    assert result.status == "failure"
