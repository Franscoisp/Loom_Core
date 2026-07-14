"""Project support: first-class projects with scoped memory (spec §6).

A project is a directory containing its own ``data/`` memory and optional
per-project continuity files. The global registry at ``~/.loom/projects.json``
tracks known projects and the active one; switching projects points the CLI at
a different memory scope without any cross-contamination.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from loom_core.locking import FileLock

LOOM_HOME = Path.home() / ".loom"
LOOM_HOME.mkdir(parents=True, exist_ok=True)
REGISTRY_PATH = LOOM_HOME / "projects.json"
ACTIVE_PATH = LOOM_HOME / "active-project"

CONTINUITY_FILES: tuple[str, ...] = (
    "PROGRESS.md",
    "TASKS.md",
    "CURRENT_FOCUS.md",
    "SESSION_LOG.md",
    "DECISIONS.md",
    "COMPLETED.md",
)


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class ProjectRecord:
    name: str
    path: str
    created: str = field(default_factory=_utcnow)
    last_active: str = field(default_factory=_utcnow)


class ProjectRegistry:
    """Manages the set of known Loom projects (spec §6)."""

    def __init__(self, registry_path: Path | None = None) -> None:
        self.path = registry_path or REGISTRY_PATH

    # --- persistence --------------------------------------------------------

    def _load(self) -> dict[str, dict[str, str]]:
        if not self.path.exists():
            return {}
        with FileLock(self.path):
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}

    def _save(self, data: dict[str, dict[str, str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(data, fh, indent=2, sort_keys=True)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    # --- operations ---------------------------------------------------------

    def register(self, name: str, path: str) -> ProjectRecord:
        record = ProjectRecord(name=name, path=Path(path).absolute().as_posix())
        data = self._load()
        data[name] = asdict(record)
        self._save(data)
        return record

    def get(self, name: str) -> ProjectRecord | None:
        raw = self._load().get(name)
        if raw is None:
            return None
        return ProjectRecord(**raw)

    def list(self) -> list[ProjectRecord]:
        return sorted(
            (ProjectRecord(**rec) for rec in self._load().values()),
            key=lambda r: r.name,
        )

    def remove(self, name: str) -> bool:
        data = self._load()
        if name not in data:
            return False
        del data[name]
        self._save(data)
        return True

    # --- active project -----------------------------------------------------

    def active_name(self) -> str | None:
        if not ACTIVE_PATH.exists():
            return None
        name = ACTIVE_PATH.read_text(encoding="utf-8").strip()
        return name or None

    def set_active(self, name: str) -> None:
        now = _utcnow()
        data = self._load()
        if name not in data:
            raise ValueError(
                f"project {name!r} is not registered; use 'loom project init {name}' first"
            )
        data[name]["last_active"] = now
        self._save(data)
        ACTIVE_PATH.write_text(name + "\n", encoding="utf-8", newline="\n")

    def active(self) -> ProjectRecord | None:
        name = self.active_name()
        if name is None:
            return None
        return self.get(name)


def resolve_project_data_dir(
    project_name: str | None = None,
    data_dir: str | os.PathLike[str] | None = None,
) -> Path:
    """Determine the data directory, respecting project scope (spec §6).

    Precedence:
    1. Explicit ``--data-dir``
    2. Active project (if any)
    3. ``LOOM_DATA_DIR`` env var
    4. ``./data`` (current working directory)
    """
    if data_dir is not None:
        return Path(data_dir)

    if project_name is not None:
        reg = ProjectRegistry()
        proj = reg.get(project_name)
        if proj is None:
            raise ValueError(f"unknown project {project_name!r}")
        return Path(proj.path) / "data"

    active = ProjectRegistry().active()
    if active is not None:
        return Path(active.path) / "data"

    env = os.environ.get("LOOM_DATA_DIR")
    if env:
        return Path(env)

    return Path.cwd() / "data"
