"""The Orchestrator: task ownership, context packs, loop dispatch (spec §6).

The Orchestrator is the *only* component allowed to grant and revoke task
ownership and to assemble the final context packs sent to models. Loops are
registered with it and request ownership through the OwnershipBroker protocol.

Ownership is persisted (spec §7) and value metrics (spec §8) are updated as a
side effect of dispatch: distillation runs, tokens saved, ownership conflicts.
"""

from __future__ import annotations

from loom_core.context import ContextPack, ContextPacker
from loom_core.loops.base import Loop, LoopResult, Task
from loom_core.metrics import MetricsStore
from loom_core.ownership import DEFAULT_TTL_SECONDS, OwnershipError, OwnershipRegistry
from loom_core.store import MemoryStore

__all__ = ["Orchestrator", "OwnershipError"]


class Orchestrator:
    """Coordinates loops, ownership, and context assembly (spec §6)."""

    def __init__(
        self,
        store: MemoryStore | None = None,
        *,
        ownership_ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self.store = store or MemoryStore()
        self.packer = ContextPacker(self.store)
        self.metrics = MetricsStore(self.store.data_dir)
        self._ownership = OwnershipRegistry(
            self.store.data_dir, ttl_seconds=ownership_ttl_seconds
        )
        self._loops: list[Loop] = []

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
        granted = self._ownership.grant(task_id, loop_name)
        if not granted:
            self.metrics.increment("ownership_conflicts")
        return granted

    def revoke(self, task_id: str, loop_name: str) -> None:
        self._ownership.revoke(task_id, loop_name)

    def heartbeat(self, loop_name: str) -> None:
        self._ownership.heartbeat(loop_name)

    def owner_of(self, task_id: str) -> str | None:
        return self._ownership.owner_of(task_id)

    # --- value metrics (spec §8) --------------------------------------------

    def record_recovery(self) -> None:
        """Record that a session started by loading from memory (spec §8)."""
        self.metrics.increment("recovery_events")

    def metrics_snapshot(self) -> dict[str, object]:
        from loom_core.metrics import compute_metrics

        return compute_metrics(self.store, self.metrics.load())

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
        self._update_metrics(loop, result)
        return result

    def _update_metrics(self, loop: Loop, result: LoopResult) -> None:
        if loop.name == "distillation" and result.status != "failure":
            self.metrics.increment("distillation_runs")
        saved = result.metrics.get("tokens_saved_estimate")
        if isinstance(saved, int) and saved > 0:
            self.metrics.increment("tokens_saved_cumulative", by=saved)
