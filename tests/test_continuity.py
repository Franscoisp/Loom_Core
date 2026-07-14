from pathlib import Path

from loom_core.continuity import SACRED_FILES, ContinuityGuard


def test_check_reports_missing(tmp_path: Path) -> None:
    guard = ContinuityGuard(tmp_path)
    missing = guard.check()
    assert set(missing) == set(SACRED_FILES)


def test_check_healthy_when_present(tmp_path: Path) -> None:
    for rel in SACRED_FILES:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("content", encoding="utf-8")
    assert ContinuityGuard(tmp_path).check() == []


def test_recreate_missing_creates_stubs(tmp_path: Path) -> None:
    guard = ContinuityGuard(tmp_path)
    report = guard.recreate_missing()
    assert set(report.recreated) == set(SACRED_FILES)
    assert guard.check() == []
    assert report.ok is False  # something was missing at check time
    # stub content marks the auto-recreation
    text = (tmp_path / "PROGRESS.md").read_text(encoding="utf-8")
    assert "AUTO-RECREATED STUB" in text
