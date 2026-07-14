"""The Orchestrator: task ownership, context packs, loop dispatch (spec §6).

The Orchestrator is the *only* component allowed to grant and revoke task
ownership and to assemble the final context packs sent to models. Loops are
registered with it and request ownership through the OwnershipBroker protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from loom_core.context import ContextPack, ContextPacker
from loom_core.loops.base import Loop, LoopResult, Task
from loom_core.store import MemoryStore


def _utcnow() -> datetime:
    return datetime.now(UTC)


class OwnershipError(RuntimeError):
    """Raised on an illegal ownership transition."""


@dataclass
class _Ownership:
    task_id: str
    loop_name: str
    since: datetime = field(default_factory=_utcnow)


class Orchestrator:
    """Coordinates loops, ownership, and context assembly (spec §6)."""

    def __init__(self, store: MemoryStore | None = None) -> None:
        self.store = store or MemoryStore()
        self.packer = ContextPacker(self.store)
        self._loops: list[Loop] = []
        self._ownership: dict[str, _Ownership] = {}
        self._heartbeats: dict[str, datetime] = {}

    # --- loop registration --------------------------------------------------

    def register(self, loop: Loop) -> None:
        """Register a loop and bind it to this orchestrator as its broker."""
        loop.bind(self)
        self._loops.append(loop)

    @property
    def loops(self) -> list[Loop]:
        return list(self._loops)

    # --- OwnershipBroker (spec §6: only the Orchestrator grants/revokes) -----

    def grant(self, task_id: str, loop_name: str) -> bool:
        current = self._ownership.get(task_id)
        if current is None:
            self._ownership[task_id] = _Ownership(task_id, loop_name)
            return True
        return current.loop_name == loop_name

    def revoke(self, task_id: str, loop_name: str) -> None:
        current = self._ownership.get(task_id)
        if current is None:
            return
        if current.loop_name != loop_name:
            raise OwnershipError(
                f"{loop_name} cannot release task {task_id} owned by "
                f"{current.loop_name}"
            )
        del self._ownership[task_id]

    def heartbeat(self, loop_name: str) -> None:
        self._heartbeats[loop_name] = _utcnow()

    def owner_of(self, task_id: str) -> str | None:
        current = self._ownership.get(task_id)
        return current.loop_name if current else None

    # --- context packing (spec §3.5) ----------------------------------------

    def context_pack(
        self,
        query: str = "",
        *,
        tags: list[str] | None = None,
        project: str | None = None,
        token_budget: int = 2000,
    ) -> ContextPack:
        """Assemble an optimized context pack from memory."""
        return self.packer.pack(
            query, tags=tags, project=project, token_budget=token_budget
        )

    # --- dispatch -----------------------------------------------------------

    def find_loop(self, task: Task) -> Loop | None:
        for loop in self._loops:
            if loop.can_handle(task):
                return loop
        return None

    def dispatch(self, task: Task) -> LoopResult:
        """Route a task to a capable loop, enforcing claim/run/release."""
        loop = self.find_loop(task)
        if loop is None:
            raise OwnershipError(f"no registered loop can handle task {task.id!r}")
        if not loop.claim(task.id):
            owner = self.owner_of(task.id)
            raise OwnershipError(
                f"{loop.name} could not claim task {task.id!r} (owned by {owner})"
            )
        try:
            loop.heartbeat()
            result = loop.run(task)
        finally:
            loop.release(task.id)
        return result
