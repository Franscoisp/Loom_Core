"""Plugin loader (spec §13).

Plugins extend Loom Core with additional tools, loops, or MCP server configs.
The initial API is small and explicit: a plugin is a Python module or package
that exposes a ``register(registry)`` function. Auto-loading is opt-in; manual
registration is the default for safety and visibility.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

from loom_core.locking import FileLock

LOOM_HOME = Path.home() / ".loom"
LOOM_HOME.mkdir(parents=True, exist_ok=True)
PLUGINS_PATH = LOOM_HOME / "plugins.json"


@dataclass
class PluginRecord:
    name: str
    path: str
    version: str = "0.1.0"
    description: str = ""
    status: str = "loaded"  # loaded | disabled | error
    tools: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)
    registered: str = ""


class PluginRegistry:
    """Tracks loaded plugins and their contributions."""

    def __init__(self) -> None:
        self.path = PLUGINS_PATH

    def _load(self) -> dict[str, dict[str, object]]:
        if not self.path.exists():
            return {}
        with FileLock(self.path):
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

    def register(self, record: PluginRecord) -> None:
        data = self._load()
        data[record.name] = asdict(record)
        self._save(data)

    def list(self) -> list[PluginRecord]:
        return [
            PluginRecord(**{k.replace(" ", "_"): v for k, v in rec.items()})  # type: ignore[arg-type]
            for rec in self._load().values()
        ]

    def get(self, name: str) -> PluginRecord | None:
        raw = self._load().get(name)
        if raw is None:
            return None
        return PluginRecord(**{k.replace(" ", "_"): v for k, v in raw.items()})  # type: ignore[arg-type]


# --- plugin loader ----------------------------------------------------------


@dataclass
class LoadedPlugin:
    record: PluginRecord
    module: ModuleType | None = None
    error: str | None = None


class PluginLoader:
    """Discover, load, and activate plugins (spec §13)."""

    def __init__(self) -> None:
        self.registry = PluginRegistry()
        self._loaded: dict[str, LoadedPlugin] = {}

    def load(
        self,
        path: str | Path,
        *,
        name: str | None = None,
        description: str = "",
    ) -> LoadedPlugin:
        """Load a single plugin by path."""
        p = Path(path).absolute()
        plugin_name = name or p.stem

        if not p.exists():
            raise FileNotFoundError(f"plugin path not found: {p}")

        try:
            spec = importlib.util.spec_from_file_location(plugin_name, str(p))
            if spec is None or spec.loader is None:
                raise ImportError(f"could not load {p}")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception as exc:
            lp = LoadedPlugin(
                record=PluginRecord(name=plugin_name, path=str(p), status="error"),
                error=str(exc),
            )
            self.registry.register(lp.record)
            self._loaded[plugin_name] = lp
            return lp

        version = getattr(mod, "__version__", "0.1.0")
        record = PluginRecord(
            name=plugin_name,
            path=str(p),
            version=version,
            description=description,
            registered=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        )
        lp = LoadedPlugin(record=record, module=mod)
        self._loaded[plugin_name] = lp
        self.registry.register(record)
        return lp

    def list(self) -> list[LoadedPlugin]:
        return list(self._loaded.values())

    def get(self, name: str) -> LoadedPlugin | None:
        return self._loaded.get(name)
