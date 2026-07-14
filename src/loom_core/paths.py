"""Filesystem layout and naming rules for memory entries (spec §3.4).

The data directory defaults to ``./data`` but can be overridden via the
``LOOM_DATA_DIR`` environment variable or an explicit argument, which keeps the
store testable against temporary directories (TASK-016).
"""

from __future__ import annotations

import os
from pathlib import Path

from loom_core.models import BaseEntry, EntryType

DEFAULT_DATA_DIRNAME = "data"
ENV_DATA_DIR = "LOOM_DATA_DIR"


def resolve_data_dir(data_dir: str | os.PathLike[str] | None = None) -> Path:
    """Resolve the data directory: explicit arg > env var > ./data."""
    if data_dir is not None:
        return Path(data_dir)
    env = os.environ.get(ENV_DATA_DIR)
    if env:
        return Path(env)
    return Path.cwd() / DEFAULT_DATA_DIRNAME


_SUBDIR: dict[str, tuple[str, ...]] = {
    EntryType.core.value: ("core",),
    EntryType.preference.value: ("core",),
    EntryType.episode.value: ("episodic",),
    EntryType.outcome.value: ("episodic",),
    EntryType.skill.value: ("procedural", "skills"),
    EntryType.tool.value: ("procedural", "tools"),
    EntryType.anti_pattern.value: ("procedural", "anti-patterns"),
    EntryType.entity.value: ("semantic", "entities"),
    EntryType.relation.value: ("semantic", "relations"),
}


def subdir_for(type_value: str) -> tuple[str, ...]:
    """Return the data/ subdirectory parts for a given entry type."""
    try:
        return _SUBDIR[type_value]
    except KeyError as exc:
        raise ValueError(f"no directory mapping for entry type {type_value!r}") from exc


def filename_for(entry: BaseEntry) -> str:
    """Build the filename for an entry per the strict naming rules (§3.4)."""
    type_value = entry.type.value if isinstance(entry.type, EntryType) else str(entry.type)

    if type_value in (EntryType.skill.value, EntryType.tool.value):
        version = getattr(entry, "version", 1)
        return f"{entry.id}-v{version}.md"

    if type_value == EntryType.core.value or type_value == EntryType.preference.value:
        return f"{entry.created:%Y%m%d}-{entry.id}.md"

    if type_value in (EntryType.episode.value, EntryType.outcome.value):
        return f"{entry.created:%Y%m%d-%H%M}-{entry.id}.md"

    return f"{entry.id}.md"


def path_for(entry: BaseEntry, data_dir: str | os.PathLike[str] | None = None) -> Path:
    """Absolute path where an entry should be stored."""
    type_value = entry.type.value if isinstance(entry.type, EntryType) else str(entry.type)
    root = resolve_data_dir(data_dir)
    return root.joinpath(*subdir_for(type_value), filename_for(entry))
