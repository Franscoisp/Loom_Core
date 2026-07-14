from pathlib import Path

import pytest

from loom_core.context import ContextPacker, estimate_tokens
from loom_core.models import parse_entry
from loom_core.store import MemoryStore


@pytest.fixture()
def store(tmp_path: Path) -> MemoryStore:
    s = MemoryStore(tmp_path / "data")
    s.write(
        parse_entry(
            {
                "id": "core-loom",
                "type": "core",
                "title": "Loom invariant",
                "source": "user",
                "status": "active",
                "tags": ["loom", "architecture"],
                "confidence": 0.95,
            }
        ),
        "Memory is the center.",
    )
    s.write(
        parse_entry(
            {
                "id": "skill-good",
                "type": "skill",
                "title": "A reliable skill",
                "source": "meta-loop",
                "status": "promoted",
                "tags": ["loom"],
                "success_count": 9,
                "failure_count": 1,
            }
        ),
        "steps here",
    )
    s.write(
        parse_entry(
            {
                "id": "unrelated",
                "type": "entity",
                "title": "Something else",
                "source": "user",
                "tags": ["other"],
            }
        ),
        "nothing to do with the query",
    )
    return s


def test_estimate_tokens_is_positive() -> None:
    assert estimate_tokens("") == 1
    assert estimate_tokens("abcd" * 10) == 10


def test_pack_prefers_tag_matches(store: MemoryStore) -> None:
    pack = ContextPacker(store).pack(tags=["loom"], token_budget=2000)
    ids = [i.entry.id for i in pack.items]
    assert "core-loom" in ids
    assert "skill-good" in ids
    # unrelated entry has no positive signal from the query tags but still gets
    # baseline recency/confidence; ensure loom-tagged items rank first.
    assert ids.index("core-loom") < ids.index("unrelated") if "unrelated" in ids else True


def test_pack_respects_token_budget(store: MemoryStore) -> None:
    pack = ContextPacker(store).pack(tags=["loom"], token_budget=5)
    assert pack.tokens_used <= 5


def test_pack_records_savings(store: MemoryStore) -> None:
    pack = ContextPacker(store).pack(tags=["loom"], token_budget=3)
    assert pack.tokens_saved_estimate >= 0


def test_pack_excludes_deprecated(store: MemoryStore) -> None:
    store.write(
        parse_entry(
            {
                "id": "old-skill",
                "type": "skill",
                "title": "Deprecated",
                "source": "meta-loop",
                "status": "deprecated",
                "tags": ["loom"],
            }
        )
    )
    pack = ContextPacker(store).pack(tags=["loom"], token_budget=5000)
    assert "old-skill" not in [i.entry.id for i in pack.items]
