"""Cross-platform advisory file locking (spec §11 / DEC-012).

Loom Core persists small JSON files (ownership, metrics, tool registry) that are
read-modify-written. A single-process run is safe, but concurrent processes
could lose updates. ``FileLock`` serializes those critical sections using an
atomic ``O_CREAT | O_EXCL`` lock file with polling and stale-lock breaking, so
it works identically on Windows and POSIX without extra dependencies.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from types import TracebackType


class LockTimeout(TimeoutError):
    """Raised when a lock cannot be acquired within the timeout."""


class FileLock:
    """An advisory lock guarding writes to ``target`` (via ``target + '.lock'``)."""

    def __init__(
        self,
        target: str | os.PathLike[str],
        *,
        timeout: float = 10.0,
        poll: float = 0.05,
        stale_after: float = 30.0,
    ) -> None:
        self.lock_path = Path(f"{os.fspath(target)}.lock")
        self.timeout = timeout
        self.poll = poll
        self.stale_after = stale_after
        self._held = False

    def acquire(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                fd = os.open(
                    self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY
                )
                try:
                    os.write(fd, str(os.getpid()).encode("ascii"))
                finally:
                    os.close(fd)
                self._held = True
                return
            except FileExistsError:
                self._break_if_stale()
                if time.monotonic() >= deadline:
                    raise LockTimeout(
                        f"could not acquire lock {self.lock_path} within "
                        f"{self.timeout}s"
                    ) from None
                time.sleep(self.poll)

    def _break_if_stale(self) -> None:
        try:
            age = time.time() - self.lock_path.stat().st_mtime
        except OSError:
            return
        if age > self.stale_after:
            try:
                self.lock_path.unlink()
            except OSError:
                pass

    def release(self) -> None:
        if self._held:
            try:
                self.lock_path.unlink()
            except OSError:
                pass
            self._held = False

    def __enter__(self) -> FileLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()
