"""Loom Core CLI.

Phase 1 exposes memory commands: write, list, show, search (TASK-014).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import frontmatter
import typer

from loom_core import __version__
from loom_core.loops.base import Task
from loom_core.loops.distillation import DistillationLoop
from loom_core.models import parse_entry
from loom_core.orchestrator import Orchestrator
from loom_core.store import LoadedEntry, MemoryStore

app = typer.Typer(help="Loom Core - local-first, memory-centric runtime.")
memory_app = typer.Typer(help="Inspect and manage Loom memory entries.")
app.add_typer(memory_app, name="memory")


@app.callback()
def main() -> None:
    """Loom Core - local-first, memory-centric runtime."""


@app.command()
def version() -> None:
    """Print the Loom Core version."""
    typer.echo(__version__)


def _fmt(loaded: LoadedEntry) -> str:
    e = loaded.entry
    return (
        f"{e.id}  [{e.type}]  {e.status}/{e.outcome}  "
        f"conf={e.confidence}  tags={','.join(e.tags) or '-'}\n"
        f"    {e.title}\n    {loaded.path}"
    )


DataDirOpt = Annotated[
    Path | None, typer.Option(help="Override the data directory.")
]


@memory_app.command("write")
def memory_write(
    from_file: Annotated[
        Path | None,
        typer.Option("--file", "-f", help="Import a Markdown+frontmatter file."),
    ] = None,
    id: Annotated[str | None, typer.Option(help="Stable, filename-safe id.")] = None,
    type: Annotated[str | None, typer.Option(help="Entry type (core, ...).")] = None,
    title: Annotated[str | None, typer.Option(help="Human-readable title.")] = None,
    source: Annotated[str | None, typer.Option(help="Knowledge source.")] = None,
    status: Annotated[str | None, typer.Option(help="draft|active|...")] = None,
    outcome: Annotated[str | None, typer.Option(help="success|failure|...")] = None,
    confidence: Annotated[float | None, typer.Option(help="0.0-1.0.")] = None,
    session_id: Annotated[
        str | None, typer.Option(help="Required for episodes.")
    ] = None,
    tag: Annotated[
        list[str] | None, typer.Option("--tag", help="Tag (repeatable).")
    ] = None,
    body: Annotated[str | None, typer.Option(help="Markdown body text.")] = None,
    body_file: Annotated[
        Path | None, typer.Option(help="Read body from a file.")
    ] = None,
    data_dir: DataDirOpt = None,
) -> None:
    """Create or import a memory entry (validated, stored at its canonical path)."""
    store = MemoryStore(data_dir)

    if from_file is not None:
        post = frontmatter.load(str(from_file))
        entry = parse_entry(dict(post.metadata))
        target = store.write(entry, post.content)
        typer.echo(f"wrote {entry.id} -> {target}")
        return

    data: dict[str, object] = {}
    for key, val in {
        "id": id,
        "type": type,
        "title": title,
        "source": source,
        "status": status,
        "outcome": outcome,
        "confidence": confidence,
        "session_id": session_id,
    }.items():
        if val is not None:
            data[key] = val
    if tag:
        data["tags"] = list(tag)

    body_text = ""
    if body_file is not None:
        body_text = body_file.read_text(encoding="utf-8")
    elif body is not None:
        body_text = body

    try:
        entry = parse_entry(data)
    except Exception as exc:  # noqa: BLE001 - surface validation errors to the user
        typer.echo(f"invalid entry: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    target = store.write(entry, body_text)
    typer.echo(f"wrote {entry.id} -> {target}")


@memory_app.command("list")
def memory_list(
    type: Annotated[str | None, typer.Option(help="Filter by type.")] = None,
    status: Annotated[str | None, typer.Option(help="Filter by status.")] = None,
    tag: Annotated[str | None, typer.Option(help="Filter by tag.")] = None,
    data_dir: DataDirOpt = None,
) -> None:
    """List memory entries, optionally filtered."""
    store = MemoryStore(data_dir)
    entries = store.list_entries(type=type, status=status, tag=tag)
    if not entries:
        typer.echo("(no matching entries)")
        return
    for loaded in entries:
        typer.echo(_fmt(loaded))


@memory_app.command("show")
def memory_show(
    entry_id: Annotated[str, typer.Argument(help="Entry id to display.")],
    data_dir: DataDirOpt = None,
) -> None:
    """Show a single entry's frontmatter and body."""
    store = MemoryStore(data_dir)
    loaded = store.get(entry_id)
    if loaded is None:
        typer.echo(f"no entry with id {entry_id!r}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"# {loaded.path}\n")
    typer.echo(loaded.entry.model_dump_json(indent=2))
    if loaded.body.strip():
        typer.echo("\n--- body ---\n")
        typer.echo(loaded.body)


@memory_app.command("search")
def memory_search(
    query: Annotated[str, typer.Argument(help="Keyword to search for.")],
    limit: Annotated[int | None, typer.Option(help="Max results.")] = None,
    data_dir: DataDirOpt = None,
) -> None:
    """Keyword-search entries by id, title, tags and body."""
    store = MemoryStore(data_dir)
    results = store.search(query, limit=limit)
    if not results:
        typer.echo("(no matches)")
        return
    for loaded in results:
        typer.echo(_fmt(loaded))


@app.command()
def pack(
    query: Annotated[str, typer.Argument(help="Query / keywords to pack around.")] = "",
    tag: Annotated[
        list[str] | None, typer.Option("--tag", help="Bias toward a tag (repeatable).")
    ] = None,
    project: Annotated[str | None, typer.Option(help="Project to prefer.")] = None,
    budget: Annotated[int, typer.Option(help="Token budget.")] = 2000,
    data_dir: DataDirOpt = None,
) -> None:
    """Assemble and print an optimized context pack from memory (spec §3.5)."""
    orch = Orchestrator(MemoryStore(data_dir))
    result = orch.context_pack(
        query, tags=tag, project=project, token_budget=budget
    )
    typer.echo(
        f"# context pack  budget={result.token_budget}  used={result.tokens_used}  "
        f"saved~={result.tokens_saved_estimate}  items={len(result.items)}"
    )
    for item in result.items:
        typer.echo(
            f"\n## {item.entry.id}  (score={item.score}, tokens={item.tokens})"
        )
        typer.echo(f"   why: {'; '.join(item.reasons)}")
        typer.echo(item.text)


@app.command()
def distill(
    payload_file: Annotated[
        Path, typer.Argument(help="JSON file describing the distillation payload.")
    ],
    data_dir: DataDirOpt = None,
) -> None:
    """Run the Distillation Loop on a JSON session payload (spec §4.2)."""
    payload = json.loads(Path(payload_file).read_text(encoding="utf-8"))
    store = MemoryStore(data_dir)
    orch = Orchestrator(store)
    orch.register(DistillationLoop(store))
    task = Task(
        id=str(payload.get("session_id", "distill-task")),
        kind="distill",
        payload=payload,
    )
    result = orch.dispatch(task)
    typer.echo(f"status: {result.status}")
    typer.echo(result.outcome_summary)
    typer.echo(f"entries written: {', '.join(result.memory_entries_written)}")
    typer.echo(f"metrics: {result.metrics}")


if __name__ == "__main__":
    app()
