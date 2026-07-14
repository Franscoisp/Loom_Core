from pathlib import Path

import pytest

from loom_core.loops.base import Task
from loom_core.loops.meta import MetaLoop
from loom_core.models import parse_entry
from loom_core.orchestrator import Orchestrator
from loom_core.registry import ToolRegistry
from loom_core.store import MemoryStore


@pytest.fixture()
def setup(tmp_path: Path) -> tuple[Orchestrator, MetaLoop, MemoryStore]:
    store = MemoryStore(tmp_path / "data")
    orch = Orchestrator(store)
    loop = MetaLoop(store)
    orch.register(loop)
    return orch, loop, store


def test_detect_low_success_skill(setup) -> None:
    orch, loop, store = setup
    store.write(
        parse_entry(
            {
                "id": "flaky",
                "type": "skill",
                "title": "Flaky skill",
                "source": "meta-loop",
                "success_count": 1,
                "failure_count": 4,
            }
        ),
        "steps",
    )
    proposals = loop.detect(min_samples=3, low_rate=0.5)
    kinds = {(p.proposal_type, p.target_id) for p in proposals}
    assert ("skill_improvement", "flaky") in kinds


def test_detect_failure_cluster(setup) -> None:
    orch, loop, store = setup
    for i in range(2):
        store.write(
            parse_entry(
                {
                    "id": f"fail-{i}",
                    "type": "outcome",
                    "title": f"Failure {i}",
                    "source": "coding-loop",
                    "outcome": "failure",
                    "tags": ["db-migration"],
                }
            )
        )
    proposals = loop.detect()
    assert any(
        p.proposal_type == "anti_pattern" and "db-migration" in p.target_id
        for p in proposals
    )


def test_detect_writes_episode(setup) -> None:
    orch, _loop, store = setup
    result = orch.dispatch(Task(id="t", kind="meta", payload={"action": "detect"}))
    assert result.status == "success"
    assert result.memory_entries_written  # an episode was written


def test_propose_new_tool_registers_candidate(setup) -> None:
    orch, _loop, store = setup
    result = orch.dispatch(
        Task(
            id="t",
            kind="meta",
            payload={
                "action": "propose",
                "proposal_type": "new_tool",
                "id": "csv-linter",
                "title": "CSV Linter",
                "spec": "Lints CSV files.",
                "steps": "1. read 2. lint",
            },
        )
    )
    assert result.status == "success"
    tool = store.get("csv-linter")
    assert tool is not None
    assert str(tool.entry.status) == "draft"
    assert store.get("use-csv-linter") is not None  # companion skill

    reg = ToolRegistry(store.data_dir)
    rec = reg.get("csv-linter")
    assert rec is not None
    assert rec.status == "candidate"


def test_skill_improvement_creates_new_version(setup) -> None:
    orch, _loop, store = setup
    store.write(
        parse_entry(
            {
                "id": "greet",
                "type": "skill",
                "title": "Greet v1",
                "source": "meta-loop",
                "status": "promoted",
                "version": 1,
            }
        ),
        "say hi",
    )
    result = orch.dispatch(
        Task(
            id="t",
            kind="meta",
            payload={
                "action": "propose",
                "proposal_type": "skill_improvement",
                "base_id": "greet",
                "title": "Greet v2",
                "steps": "say hello nicely",
            },
        )
    )
    assert result.metrics["version"] == 2
    versions = store.versions("greet")
    assert {int(v.entry.version) for v in versions} == {1, 2}  # type: ignore[attr-defined]


def test_evaluate_promotion_requires_evidence(setup) -> None:
    orch, _loop, store = setup
    store.write(
        parse_entry(
            {
                "id": "cand",
                "type": "skill",
                "title": "Candidate",
                "source": "meta-loop",
                "status": "draft",
            }
        ),
        "steps",
    )
    blocked = orch.dispatch(
        Task(
            id="t",
            kind="meta",
            payload={"action": "evaluate", "target_id": "cand", "decision": "promote"},
        )
    )
    assert blocked.status == "partial"
    assert str(store.get("cand").entry.status) == "draft"  # type: ignore[union-attr]

    promoted = orch.dispatch(
        Task(
            id="t2",
            kind="meta",
            payload={
                "action": "evaluate",
                "target_id": "cand",
                "decision": "promote",
                "evidence": "3 successful uses",
                "expected_improvement": "faster greetings",
                "success_metric": "success_rate > 0.9",
            },
        )
    )
    assert promoted.status == "success"
    assert str(store.get("cand").entry.status) == "promoted"  # type: ignore[union-attr]


def test_evaluate_deprecate_tool_updates_registry(setup) -> None:
    orch, _loop, store = setup
    orch.dispatch(
        Task(
            id="t",
            kind="meta",
            payload={
                "action": "propose",
                "proposal_type": "new_tool",
                "id": "old-tool",
                "title": "Old tool",
            },
        )
    )
    orch.dispatch(
        Task(
            id="t2",
            kind="meta",
            payload={
                "action": "evaluate",
                "target_id": "old-tool",
                "decision": "deprecate",
            },
        )
    )
    assert str(store.get("old-tool").entry.status) == "deprecated"  # type: ignore[union-attr]
    assert ToolRegistry(store.data_dir).get("old-tool").status == "deprecated"  # type: ignore[union-attr]
