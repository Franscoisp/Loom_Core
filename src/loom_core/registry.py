"""Tool registry & discovery (spec §5.4).

A simple JSON registry at ``data/procedural/tools/registry.json`` that records
the tools the system knows about, their version and lifecycle status, and the
skill that documents how to use them. Kept reconstructible and human-readable.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from loom_core.locking import FileLock
from loom_core.paths import resolve_data_dir

REGISTRY_RELPATH = ("procedural", "tools", "registry.json")


@dataclass
class ToolRecord:
    id: str
    version: int
    status: str  # "candidate" | "promoted" | "deprecated"
    skill_id: str = ""
    spec: str = ""
    registered: str = ""


class ToolRegistry:
    """Discoverable registry of tools (spec §5.4)."""

    def __init__(self, data_dir: str | os.PathLike[str] | None = None) -> None:
        self.path = resolve_data_dir(data_dir).joinpath(*REGISTRY_RELPATH)

    def _load(self) -> dict[str, dict[str, object]]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}

    def _save(self, data: dict[str, dict[str, object]]) -> None:
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

    def register(self, record: ToolRecord) -> ToolRecord:
        if not record.registered:
            record.registered = datetime.now(UTC).isoformat().replace(
                "+00:00", "Z"
            )
        with FileLock(self.path):
            data = self._load()
            data[record.id] = asdict(record)
            self._save(data)
        return record

    def set_status(self, tool_id: str, status: str) -> bool:
        with FileLock(self.path):
            data = self._load()
            if tool_id not in data:
                return False
            data[tool_id]["status"] = status
            self._save(data)
        return True

    def get(self, tool_id: str) -> ToolRecord | None:
        data = self._load()
        if tool_id not in data:
            return None
        return ToolRecord(**{k: v for k, v in data[tool_id].items()})  # type: ignore[arg-type]

    def list(self) -> list[ToolRecord]:
        return [
            ToolRecord(**{k: v for k, v in rec.items()})  # type: ignore[arg-type]
            for rec in self._load().values()
        ]
