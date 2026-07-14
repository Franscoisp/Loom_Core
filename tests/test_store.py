from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from loom_core.models import parse_entry
from loom_core.store import MemoryStore


def _core(store_id: str, **kw: object) -> dict:
    base = {"id": store_id, "type": "core", "title": f"Title {store_id}", "source": "user"}
    base.update(kw)
    return base


@pytest.fixture()
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(tmp_path / "data")


def test_write_places_file_at_canonical_path(store: MemoryStore) -> None:
    e = parse_entry(
        _core("inv-1", created=datetime(2026, 7, 14, 9, 30, tzinfo=UTC))
    )
    path = store.write(e, "body text")
    assert path.parent.name == "core"
    assert path.name == "20260714-inv-1.md"
    assert path.exists()


def test_write_is_round_trippable(store: MemoryStore) -> None:
    e = parse_entry(_core("inv-2", tags=["a", "b"]))
    path = store.write(e, "hello world")
    loaded = store.read(path)
    assert loaded.entry.id == "inv-2"
    assert loaded.entry.tags == ["a", "b"]
    assert loaded.body.strip() == "hello world"


def test_skill_filename_is_versioned(store: MemoryStore) -> None:
    e = parse_entry(
        {
            "id": "make-tea",
            "type": "skill",
            "title": "Make tea",
            "source": "meta-loop",
            "version": 2,
        }
    )
    path = store.write(e)
    assert path.parent.parts[-2:] == ("procedural", "skills")
    assert path.name == "make-tea-v2.md"


def test_write_is_atomic_no_tmp_left(store: MemoryStore) -> None:
    e = parse_entry(_core("inv-3"))
    store.write(e)
    leftovers = list(store.data_dir.rglob("*.tmp"))
    assert leftovers == []


def test_list_and_filter(store: MemoryStore) -> None:
    store.write(parse_entry(_core("a", tags=["x"])))
    store.write(parse_entry(_core("b", tags=["y"], status="active")))
    store.write(
        parse_entry(
            {
                "id": "ep",
                "type": "episode",
                "title": "E",
                "source": "user",
                "session_id": "s1",
            }
        )
    )
    assert len(store.list_entries()) == 3
    assert len(store.list_entries(type="core")) == 2
    assert len(store.list_entries(status="active")) == 1
    assert len(store.list_entries(tag="x")) == 1
    assert store.get("b") is not None
    assert store.get("missing") is None


def test_search_ranks_title_over_body(store: MemoryStore) -> None:
    store.write(parse_entry(_core("hit-title", title="Loom memory design")))
    store.write(parse_entry(_core("hit-body")), body="a note about loom internals")
    results = store.search("loom")
    assert [r.entry.id for r in results][0] == "hit-title"
    assert len(results) == 2


def test_search_empty_query_returns_nothing(store: MemoryStore) -> None:
    store.write(parse_entry(_core("a")))
    assert store.search("   ") == []


def test_read_rejects_malformed_file(store: MemoryStore, tmp_path: Path) -> None:
    bad = store.data_dir / "core" / "bad.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("---\ntype: core\ntitle: T\n---\nno id or source\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        store.read(bad)
