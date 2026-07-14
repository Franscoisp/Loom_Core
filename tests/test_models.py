from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from loom_core.models import (
    EpisodeEntry,
    SkillEntry,
    parse_entry,
)


def test_core_entry_defaults() -> None:
    e = parse_entry({"id": "inv-1", "type": "core", "title": "Invariant", "source": "user"})
    assert e.type == "core"
    assert e.status == "draft"
    assert e.outcome == "unknown"
    assert 0.0 <= e.confidence <= 1.0
    assert e.created.tzinfo is not None


def test_unknown_type_rejected() -> None:
    with pytest.raises(ValueError):
        parse_entry({"id": "x", "type": "banana", "title": "T", "source": "user"})


def test_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_entry(
            {"id": "x", "type": "core", "title": "T", "source": "user", "bogus": 1}
        )


def test_missing_required_field_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_entry({"id": "x", "type": "core", "title": "T"})  # no source


def test_confidence_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_entry(
            {"id": "x", "type": "core", "title": "T", "source": "user", "confidence": 2}
        )


def test_id_must_be_filename_safe() -> None:
    with pytest.raises(ValidationError):
        parse_entry({"id": "bad id/x", "type": "core", "title": "T", "source": "user"})


def test_episode_requires_session_id() -> None:
    with pytest.raises(ValidationError):
        parse_entry({"id": "ep1", "type": "episode", "title": "T", "source": "user"})
    ep = parse_entry(
        {
            "id": "ep1",
            "type": "episode",
            "title": "T",
            "source": "user",
            "session_id": "2026-07-14-01",
        }
    )
    assert isinstance(ep, EpisodeEntry)
    assert ep.session_id == "2026-07-14-01"


def test_skill_success_rate_is_recomputed() -> None:
    s = parse_entry(
        {
            "id": "skill-a",
            "type": "skill",
            "title": "A skill",
            "source": "meta-loop",
            "success_count": 3,
            "failure_count": 1,
            "success_rate": 0.99,  # wrong on purpose
        }
    )
    assert isinstance(s, SkillEntry)
    assert s.success_rate == 0.75


def test_datetime_serializes_to_z() -> None:
    e = parse_entry(
        {
            "id": "x",
            "type": "core",
            "title": "T",
            "source": "user",
            "created": datetime(2026, 7, 14, 12, 0, tzinfo=UTC),
        }
    )
    dumped = e.model_dump(mode="json")
    assert dumped["created"] == "2026-07-14T12:00:00Z"
