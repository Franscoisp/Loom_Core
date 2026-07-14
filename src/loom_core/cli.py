"""Loom Core CLI (skeleton).

Real commands (memory write/list/show, distill, etc.) arrive in Phase 1.
This skeleton exists so the `loom` entry point and test harness are wired up.
"""

from __future__ import annotations

import typer

from loom_core import __version__

app = typer.Typer(help="Loom Core - local-first, memory-centric runtime.")


@app.command()
def version() -> None:
    """Print the Loom Core version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
