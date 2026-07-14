"""Persistent task-ownership registry with heartbeat reclamation (spec §6, §7).

The Orchestrator is the only component that mutates ownership, but persisting it
to ``data/ownership.json`` means ownership survives process restarts and a
crashed loop's tasks can be reclaimed once its heartbeat goes stale (spec §7,
partial session crashes). Supersedes the in-memory approach in DEC-004.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime

from loom_core.locking import FileLock
from loom_core.store import MemoryStore

OWNERSHIP_FILENAME = "ownership.json"
DEFAULT_TTL_SECONDS = 3600


class OwnershipError(RuntimeError):
    """Raised on an illegal ownership transition."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


class OwnershipRegistry:
    """File-backed ownership map: task_id -> {loop_name, since, last_heartbeat}."""

    def __init__(
        self,
        data_dir: str | os.PathLike[str] | None = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self.path = MemoryStore(data_dir).data_dir / OWNERSHIP_FILENAME
        self.ttl_seconds = ttl_seconds

    def _load(self) -> dict[str, dict[str, str]]:
        if not self.path.exists():
            return {}
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

    def _is_stale(self, record: dict[str, str]) -> bool:
        try:
            last = _parse(record["last_heartbeat"])
        except (KeyError, ValueError):
            return True
        return (_utcnow() - last).total_seconds() > self.ttl_seconds

    def grant(self, task_id: str, loop_name: str) -> bool:
        with FileLock(self.path):
            data = self._load()
            record = data.get(task_id)
            now = _iso(_utcnow())
            if (
                record is None
                or record.get("loop_name") == loop_name
                or self._is_stale(record)
            ):
                data[task_id] = {
                    "loop_name": loop_name,
                    "since": record["since"]
                    if record and record.get("loop_name") == loop_name
                    else now,
                    "last_heartbeat": now,
                }
                self._save(data)
                return True
            return False

    def revoke(self, task_id: str, loop_name: str) -> None:
        with FileLock(self.path):
            data = self._load()
            record = data.get(task_id)
            if record is None:
                return
            if record.get("loop_name") != loop_name:
                raise OwnershipError(
                    f"{loop_name} cannot release task {task_id} owned by "
                    f"{record.get('loop_name')}"
                )
            del data[task_id]
            self._save(data)

    def heartbeat(self, loop_name: str) -> None:
        with FileLock(self.path):
            data = self._load()
            now = _iso(_utcnow())
            changed = False
            for record in data.values():
                if record.get("loop_name") == loop_name:
                    record["last_heartbeat"] = now
                    changed = True
            if changed:
                self._save(data)

    def owner_of(self, task_id: str) -> str | None:
        record = self._load().get(task_id)
        return record.get("loop_name") if record else None
