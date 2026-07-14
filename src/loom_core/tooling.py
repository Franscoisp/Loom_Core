"""Executable tool framework (spec §4.4.6).

A *tool* in the registry is knowledge (spec, version, status). This module lets
a tool also have a runnable Python implementation. Tools start as ``candidate``
and are gated: candidate tools only run when explicitly allowed, and only
``promoted`` tools run freely (spec §4.4.6). Every run records an outcome entry
and updates the tool's success/failure statistics.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from loom_core.models import parse_entry
from loom_core.registry import ToolRecord, ToolRegistry
from loom_core.store import MemoryStore

ToolCallable = Callable[[dict[str, object]], dict[str, object]]


class ToolNotFoundError(RuntimeError):
    pass


class ToolNotAllowedError(RuntimeError):
    """Raised when a candidate tool is invoked without explicit permission."""


@dataclass
class ToolRun:
    tool_id: str
    ok: bool
    output: dict[str, object]
    outcome_entry_id: str


def _slug_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


class ToolExecutor:
    """Register, gate, and invoke executable tools (spec §4.4.6)."""

    def __init__(
        self, store: MemoryStore, registry: ToolRegistry | None = None
    ) -> None:
        self.store = store
        self.registry = registry or ToolRegistry(store.data_dir)
        self._fns: dict[str, ToolCallable] = {}

    def register(
        self,
        tool_id: str,
        fn: ToolCallable,
        *,
        description: str = "",
        auto_register: bool = True,
    ) -> None:
        """Bind a callable to a tool id; register it as candidate if unknown."""
        self._fns[tool_id] = fn
        if auto_register and self.registry.get(tool_id) is None:
            self.registry.register(
                ToolRecord(id=tool_id, version=1, status="candidate", spec=description)
            )

    def available(self) -> list[str]:
        return sorted(self._fns)

    def run(
        self,
        tool_id: str,
        payload: dict[str, object] | None = None,
        *,
        allow_candidate: bool = False,
    ) -> ToolRun:
        fn = self._fns.get(tool_id)
        if fn is None:
            raise ToolNotFoundError(f"no executable registered for tool {tool_id!r}")

        record = self.registry.get(tool_id)
        status = record.status if record else "unregistered"
        if status != "promoted" and not allow_candidate:
            raise ToolNotAllowedError(
                f"tool {tool_id!r} is '{status}'; pass allow_candidate=True to run "
                f"it before promotion (spec §4.4.6)"
            )

        ok = True
        try:
            output = fn(payload or {})
        except Exception as exc:  # noqa: BLE001 - record failures as outcomes
            ok = False
            output = {"error": str(exc)}

        outcome_id = f"toolrun-{tool_id}-{_slug_stamp()}"
        entry = parse_entry(
            {
                "id": outcome_id,
                "type": "outcome",
                "title": f"Tool run: {tool_id}",
                "status": "active",
                "outcome": "success" if ok else "failure",
                "confidence": 0.9,
                "tags": ["tool-run", tool_id],
                "related": [tool_id],
                "source": "tool",
                "provenance": f"ToolExecutor.run({tool_id})",
            }
        )
        self.store.write(entry, f"payload={payload}\noutput={output}")
        self.store.update_stats(tool_id, "success" if ok else "failure")
        return ToolRun(tool_id=tool_id, ok=ok, output=output, outcome_entry_id=outcome_id)


# --- built-in example tools -------------------------------------------------


def _tool_frontmatter_linter(store: MemoryStore) -> ToolCallable:
    def run(payload: dict[str, object]) -> dict[str, object]:
        checked = 0
        malformed: list[str] = []
        for path in store.iter_files():
            checked += 1
            try:
                store.read(path)
            except Exception as exc:  # noqa: BLE001
                malformed.append(f"{path}: {exc}")
        return {"checked": checked, "malformed": malformed, "ok": not malformed}

    return run


def _tool_memory_summary(store: MemoryStore) -> ToolCallable:
    def run(payload: dict[str, object]) -> dict[str, object]:
        by_type: dict[str, int] = {}
        for loaded in store.list_entries():
            key = str(loaded.entry.type)
            by_type[key] = by_type.get(key, 0) + 1
        return {"total": sum(by_type.values()), "by_type": by_type}

    return run


def build_default_executor(store: MemoryStore) -> ToolExecutor:
    """A ToolExecutor pre-loaded with Loom's built-in tools."""
    ex = ToolExecutor(store)
    ex.register(
        "frontmatter-linter",
        _tool_frontmatter_linter(store),
        description="Validate YAML frontmatter of every memory file.",
    )
    ex.register(
        "memory-summary",
        _tool_memory_summary(store),
        description="Summarize memory entry counts by type.",
    )
    return ex
