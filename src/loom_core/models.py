"""Loom Core memory entry models (spec §3.3).

Every memory file is YAML frontmatter (these models) + a Markdown body.
Models are strict: unknown fields are rejected so malformed entries fail loudly
(TASK-015). Datetimes are timezone-aware and serialize to ISO 8601 with 'Z'.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


class EntryType(StrEnum):
    """The `type` field of a memory entry (spec §3.3)."""

    core = "core"
    episode = "episode"
    skill = "skill"
    anti_pattern = "anti-pattern"
    entity = "entity"
    relation = "relation"
    outcome = "outcome"
    preference = "preference"
    tool = "tool"


class Status(StrEnum):
    draft = "draft"
    active = "active"
    promoted = "promoted"
    deprecated = "deprecated"
    rejected = "rejected"


class Outcome(StrEnum):
    success = "success"
    failure = "failure"
    partial = "partial"
    unknown = "unknown"
    not_applicable = "not_applicable"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class BaseEntry(BaseModel):
    """Common frontmatter shared by every memory entry (spec §3.3)."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    id: str = Field(min_length=1)
    type: EntryType
    title: str = Field(min_length=1)
    created: datetime = Field(default_factory=_utcnow)
    updated: datetime = Field(default_factory=_utcnow)
    status: Status = Status.draft
    outcome: Outcome = Outcome.unknown
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    source: str = Field(min_length=1)
    provenance: str = ""

    @field_validator("id")
    @classmethod
    def _id_is_slug_safe(cls, v: str) -> str:
        if any(c in v for c in '/\\:*?"<>| '):
            raise ValueError(
                "id must be filename-safe (no spaces, slashes, or reserved chars)"
            )
        return v

    @field_validator("created", "updated")
    @classmethod
    def _ensure_tz(cls, v: datetime) -> datetime:
        return v if v.tzinfo is not None else v.replace(tzinfo=UTC)

    @field_serializer("created", "updated", when_used="json")
    def _ser_dt(self, v: datetime) -> str:
        return _iso_z(v)


def _iso_z(v: datetime) -> str:
    return v.astimezone(UTC).isoformat().replace("+00:00", "Z")


class _StatsMixin(BaseModel):
    """Usage/outcome statistics shared by skills and tools (spec §3.3)."""

    version: int = Field(default=1, ge=1)
    success_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    last_used: datetime | None = None
    inputs: str = ""
    outputs: str = ""
    steps: str = ""
    evaluation_notes: str = ""

    @model_validator(mode="after")
    def _recompute_success_rate(self) -> _StatsMixin:
        total = self.success_count + self.failure_count
        object.__setattr__(
            self,
            "success_rate",
            round(self.success_count / total, 4) if total else 0.0,
        )
        return self

    @field_serializer("last_used", when_used="json")
    def _ser_last_used(self, v: datetime | None) -> str | None:
        return _iso_z(v) if v is not None else None


class CoreEntry(BaseEntry):
    type: Literal[EntryType.core] = EntryType.core


class PreferenceEntry(BaseEntry):
    type: Literal[EntryType.preference] = EntryType.preference


class OutcomeEntry(BaseEntry):
    type: Literal[EntryType.outcome] = EntryType.outcome


class AntiPatternEntry(BaseEntry):
    type: Literal[EntryType.anti_pattern] = EntryType.anti_pattern


class EntityEntry(BaseEntry):
    type: Literal[EntryType.entity] = EntryType.entity


class RelationEntry(BaseEntry):
    type: Literal[EntryType.relation] = EntryType.relation


class EpisodeEntry(BaseEntry):
    type: Literal[EntryType.episode] = EntryType.episode
    session_id: str = Field(min_length=1)
    related_tasks: list[str] = Field(default_factory=list)


class SkillEntry(_StatsMixin, BaseEntry):
    type: Literal[EntryType.skill] = EntryType.skill


class ToolEntry(_StatsMixin, BaseEntry):
    type: Literal[EntryType.tool] = EntryType.tool


AnyEntry = Annotated[
    CoreEntry
    | PreferenceEntry
    | OutcomeEntry
    | AntiPatternEntry
    | EntityEntry
    | RelationEntry
    | EpisodeEntry
    | SkillEntry
    | ToolEntry,
    Field(discriminator="type"),
]


_TYPE_TO_MODEL: dict[str, type[BaseEntry]] = {
    EntryType.core.value: CoreEntry,
    EntryType.preference.value: PreferenceEntry,
    EntryType.outcome.value: OutcomeEntry,
    EntryType.anti_pattern.value: AntiPatternEntry,
    EntryType.entity.value: EntityEntry,
    EntryType.relation.value: RelationEntry,
    EntryType.episode.value: EpisodeEntry,
    EntryType.skill.value: SkillEntry,
    EntryType.tool.value: ToolEntry,
}


def model_for_type(type_value: str) -> type[BaseEntry]:
    """Return the model class for a given `type` string, or raise ValueError."""
    try:
        return _TYPE_TO_MODEL[type_value]
    except KeyError as exc:
        valid = ", ".join(sorted(_TYPE_TO_MODEL))
        raise ValueError(
            f"unknown entry type {type_value!r}; expected one of: {valid}"
        ) from exc


def parse_entry(data: dict[str, object]) -> BaseEntry:
    """Validate a frontmatter dict into the correct entry model.

    Raises pydantic.ValidationError (or ValueError for unknown type) on
    malformed input (TASK-015).
    """
    type_value = data.get("type")
    if not isinstance(type_value, str):
        raise ValueError("entry is missing a string 'type' field")
    return model_for_type(type_value).model_validate(data)
