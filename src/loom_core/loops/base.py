"""Loom Core loop framework: Task, LoopResult and the Loop interface (spec §4.1).

Every loop is a client of the memory. The Orchestrator (spec §6) is the only
component allowed to grant or revoke task ownership; loops request ownership
through an :class:`OwnershipBroker` rather than mutating shared state directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class Task:
    """A unit of work handed to a loop."""

    id: str
    kind: str
    payload: dict[str, object] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    project: str | None = None
    created: datetime = field(default_factory=_utcnow)


@dataclass
class LoopResult:
    """The required result of running a loop (spec §4.1)."""

    status: str  # "success" | "failure" | "partial"
    outcome_summary: str
    memory_entries_written: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    lessons: str = ""
    metrics: dict[str, object] = field(default_factory=dict)

    VALID_STATUS = frozenset({"success", "failure", "partial"})

    def __post_init__(self) -> None:
        if self.status not in self.VALID_STATUS:
            raise ValueError(
                f"invalid status {self.status!r}; expected one of "
                f"{sorted(self.VALID_STATUS)}"
            )


@runtime_checkable
class OwnershipBroker(Protocol):
    """What a loop needs from the Orchestrator to manage ownership (spec §6)."""

    def grant(self, task_id: str, loop_name: str) -> bool: ...

    def revoke(self, task_id: str, loop_name: str) -> None: ...

    def heartbeat(self, loop_name: str) -> None: ...


class Loop(ABC):
    """Common loop interface (spec §4.1).

    Concrete loops implement :meth:`can_handle` and :meth:`run`. Ownership is
    brokered: :meth:`claim`/:meth:`release` delegate to the Orchestrator.
    """

    name: str = "loop"

    def __init__(self, broker: OwnershipBroker | None = None) -> None:
        self._broker = broker
        self._claimed: set[str] = set()

    def bind(self, broker: OwnershipBroker) -> None:
        """Attach the ownership broker (called by the Orchestrator on register)."""
        self._broker = broker

    @abstractmethod
    def can_handle(self, task: Task) -> bool:
        """Return True if this loop can handle the given task."""

    @abstractmethod
    def run(self, task: Task) -> LoopResult:
        """Execute the task and return a LoopResult."""

    def claim(self, task_id: str) -> bool:
        """Request ownership of a task via the broker."""
        if self._broker is None:
            raise RuntimeError(f"{self.name}: no ownership broker bound")
        granted = self._broker.grant(task_id, self.name)
        if granted:
            self._claimed.add(task_id)
        return granted

    def release(self, task_id: str) -> None:
        """Release ownership of a task via the broker."""
        if self._broker is None:
            raise RuntimeError(f"{self.name}: no ownership broker bound")
        self._broker.revoke(task_id, self.name)
        self._claimed.discard(task_id)

    def heartbeat(self) -> None:
        """Signal liveness to the broker."""
        if self._broker is not None:
            self._broker.heartbeat(self.name)
