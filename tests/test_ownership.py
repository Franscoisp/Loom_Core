from pathlib import Path

import pytest

from loom_core.ownership import OwnershipError, OwnershipRegistry


def test_grant_persists_and_blocks_others(tmp_path: Path) -> None:
    reg = OwnershipRegistry(tmp_path / "data")
    assert reg.grant("t1", "a") is True
    # a fresh instance reads persisted state
    assert OwnershipRegistry(tmp_path / "data").owner_of("t1") == "a"
    assert reg.grant("t1", "b") is False
    assert reg.grant("t1", "a") is True  # idempotent for owner


def test_revoke_requires_owner(tmp_path: Path) -> None:
    reg = OwnershipRegistry(tmp_path / "data")
    reg.grant("t1", "a")
    with pytest.raises(OwnershipError):
        reg.revoke("t1", "b")
    reg.revoke("t1", "a")
    assert reg.owner_of("t1") is None


def test_stale_heartbeat_is_reclaimable(tmp_path: Path) -> None:
    reg = OwnershipRegistry(tmp_path / "data", ttl_seconds=0)
    reg.grant("t1", "a")
    # ttl=0 => any prior heartbeat is immediately stale, so b can reclaim
    assert reg.grant("t1", "b") is True
    assert reg.owner_of("t1") == "b"


def test_heartbeat_keeps_ownership_fresh(tmp_path: Path) -> None:
    reg = OwnershipRegistry(tmp_path / "data", ttl_seconds=3600)
    reg.grant("t1", "a")
    reg.heartbeat("a")
    assert reg.grant("t1", "b") is False
