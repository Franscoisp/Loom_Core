import threading
from pathlib import Path

import pytest

from loom_core.locking import FileLock, LockTimeout
from loom_core.metrics import MetricsStore
from loom_core.store import MemoryStore


def test_lock_acquire_release(tmp_path: Path) -> None:
    target = tmp_path / "x.json"
    lock = FileLock(target)
    lock.acquire()
    assert lock.lock_path.exists()
    lock.release()
    assert not lock.lock_path.exists()


def test_lock_context_manager(tmp_path: Path) -> None:
    target = tmp_path / "x.json"
    with FileLock(target) as lock:
        assert lock.lock_path.exists()
    assert not (tmp_path / "x.json.lock").exists()


def test_lock_times_out_when_held(tmp_path: Path) -> None:
    target = tmp_path / "x.json"
    held = FileLock(target)
    held.acquire()
    try:
        with pytest.raises(LockTimeout):
            FileLock(target, timeout=0.2, poll=0.02).acquire()
    finally:
        held.release()


def test_stale_lock_is_broken(tmp_path: Path) -> None:
    target = tmp_path / "x.json"
    stale = FileLock(target)
    stale.acquire()  # leak it (never released)
    # stale_after=0 => the existing lock is immediately considered stale
    FileLock(target, timeout=1.0, poll=0.02, stale_after=0.0).acquire()


def test_concurrent_increments_are_not_lost(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "data")
    ms = MetricsStore(store.data_dir)

    def worker() -> None:
        for _ in range(20):
            ms.increment("distillation_runs")

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert ms.load().distillation_runs == 100
