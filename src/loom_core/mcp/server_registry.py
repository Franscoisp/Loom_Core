"""MCP server config registry (spec §13).

Stores known MCP server configurations under ~/.loom/mcp_servers.json so they
can be started, listed, and managed without repeating CLI arguments.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from loom_core.locking import FileLock

LOOM_HOME = Path.home() / ".loom"
LOOM_HOME.mkdir(parents=True, exist_ok=True)
MCP_SERVERS_PATH = LOOM_HOME / "mcp_servers.json"


@dataclass
class MCPServerRecord:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    description: str = ""


class MCPServerRegistry:
    """Persist known MCP server configurations."""

    def __init__(self) -> None:
        self.path = MCP_SERVERS_PATH

    def _load(self) -> dict[str, dict[str, object]]:
        if not self.path.exists():
            return {}
        with FileLock(self.path):
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        return raw

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

    def add(self, record: MCPServerRecord) -> MCPServerRecord:
        data = self._load()
        data[record.name] = asdict(record)
        self._save(data)
        return record

    def list(self) -> list[MCPServerRecord]:
        return [
            MCPServerRecord(
                name=v.get("name", ""),  # type: ignore[arg-type]
                command=v.get("command", ""),  # type: ignore[arg-type]
                args=v.get("args", []),  # type: ignore[arg-type]
                env=v.get("env", {}),  # type: ignore[arg-type]
                description=v.get("description", ""),  # type: ignore[arg-type]
            )
            for v in self._load().values()
        ]

    def get(self, name: str) -> MCPServerRecord | None:
        raw = self._load().get(name)
        if raw is None:
            return None
        return MCPServerRecord(
            name=raw.get("name", ""),  # type: ignore[arg-type]
            command=raw.get("command", ""),  # type: ignore[arg-type]
            args=raw.get("args", []),  # type: ignore[arg-type]
            env=raw.get("env", {}),  # type: ignore[arg-type]
            description=raw.get("description", ""),  # type: ignore[arg-type]
        )

    def remove(self, name: str) -> bool:
        data = self._load()
        if name not in data:
            return False
        del data[name]
        self._save(data)
        return True
