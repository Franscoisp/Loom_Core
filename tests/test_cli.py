from pathlib import Path

from typer.testing import CliRunner

from loom_core.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.0.1"


def test_write_list_show_search_roundtrip(tmp_path: Path) -> None:
    data_dir = str(tmp_path / "data")

    r = runner.invoke(
        app,
        [
            "memory", "write",
            "--id", "note-1",
            "--type", "core",
            "--title", "First note",
            "--source", "user",
            "--tag", "phase-1",
            "--body", "the loom body",
            "--data-dir", data_dir,
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert "wrote note-1" in r.stdout

    r = runner.invoke(app, ["memory", "list", "--data-dir", data_dir])
    assert r.exit_code == 0
    assert "note-1" in r.stdout

    r = runner.invoke(app, ["memory", "show", "note-1", "--data-dir", data_dir])
    assert r.exit_code == 0
    assert "First note" in r.stdout
    assert "the loom body" in r.stdout

    r = runner.invoke(app, ["memory", "search", "loom", "--data-dir", data_dir])
    assert r.exit_code == 0
    assert "note-1" in r.stdout


def test_write_invalid_entry_exits_nonzero(tmp_path: Path) -> None:
    r = runner.invoke(
        app,
        [
            "memory", "write",
            "--id", "x",
            "--type", "banana",
            "--title", "T",
            "--source", "user",
            "--data-dir", str(tmp_path / "data"),
        ],
    )
    assert r.exit_code == 1
    assert "invalid entry" in r.stdout + str(r.stderr)


def test_show_missing_exits_nonzero(tmp_path: Path) -> None:
    r = runner.invoke(app, ["memory", "show", "nope", "--data-dir", str(tmp_path / "data")])
    assert r.exit_code == 1
