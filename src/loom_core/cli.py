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
from loom_core.continuity import ContinuityGuard
from loom_core.loops.base import Task
from loom_core.loops.coding_support import CodingSupportLoop
from loom_core.loops.distillation import DistillationLoop
from loom_core.loops.meta import MetaLoop
from loom_core.metrics import MetricsStore, compute_metrics
from loom_core.models import parse_entry
from loom_core.orchestrator import Orchestrator
from loom_core.registry import ToolRegistry
from loom_core.store import LoadedEntry, MemoryStore
from loom_core.tooling import (
    ToolNotAllowedError,
    ToolNotFoundError,
    build_default_executor,
)

app = typer.Typer(help="Loom Core - local-first, memory-centric runtime.")
memory_app = typer.Typer(help="Inspect and manage Loom memory entries.")
meta_app = typer.Typer(help="Self-improvement: detect, propose, evaluate.")
tools_app = typer.Typer(help="Inspect and run tools.")
app.add_typer(memory_app, name="memory")
app.add_typer(meta_app, name="meta")
app.add_typer(tools_app, name="tools")


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


def _run_meta(payload: dict[str, object], data_dir: Path | None) -> None:
    store = MemoryStore(data_dir)
    orch = Orchestrator(store)
    orch.register(MetaLoop(store))
    task = Task(id=str(payload.get("session_id", "meta-task")), kind="meta", payload=payload)
    result = orch.dispatch(task)
    typer.echo(f"status: {result.status}")
    typer.echo(result.outcome_summary)
    if result.memory_entries_written:
        typer.echo(f"entries written: {', '.join(result.memory_entries_written)}")
    typer.echo(f"metrics: {result.metrics}")


@meta_app.command("detect")
def meta_detect(
    min_samples: Annotated[int, typer.Option(help="Min uses before judging a skill.")] = 3,
    low_rate: Annotated[float, typer.Option(help="Success-rate threshold.")] = 0.5,
    data_dir: DataDirOpt = None,
) -> None:
    """Scan memory for capability gaps and repeated failures (spec §4.4.2)."""
    _run_meta(
        {"action": "detect", "min_samples": min_samples, "low_rate": low_rate},
        data_dir,
    )


@meta_app.command("run")
def meta_run(
    payload_file: Annotated[
        Path, typer.Argument(help="JSON payload for a meta action (propose/evaluate).")
    ],
    data_dir: DataDirOpt = None,
) -> None:
    """Run an arbitrary meta action (propose/evaluate) from a JSON payload."""
    payload = json.loads(Path(payload_file).read_text(encoding="utf-8"))
    _run_meta(payload, data_dir)


@tools_app.command("list")
def tools_list(data_dir: DataDirOpt = None) -> None:
    """List registered tools and their lifecycle status (spec §5.4)."""
    records = ToolRegistry(data_dir).list()
    if not records:
        typer.echo("(no registered tools)")
        return
    for rec in records:
        typer.echo(
            f"{rec.id}  v{rec.version}  [{rec.status}]  skill={rec.skill_id or '-'}"
        )


@tools_app.command("run")
def tools_run(
    tool_id: Annotated[str, typer.Argument(help="Tool id to run.")],
    payload_file: Annotated[
        Path | None, typer.Option("--payload", help="JSON payload file.")
    ] = None,
    allow_candidate: Annotated[
        bool, typer.Option(help="Allow running a non-promoted (candidate) tool.")
    ] = False,
    data_dir: DataDirOpt = None,
) -> None:
    """Run an executable tool, gated by lifecycle status (spec §4.4.6)."""
    store = MemoryStore(data_dir)
    executor = build_default_executor(store)
    payload = (
        json.loads(Path(payload_file).read_text(encoding="utf-8"))
        if payload_file
        else {}
    )
    try:
        run = executor.run(tool_id, payload, allow_candidate=allow_candidate)
    except (ToolNotFoundError, ToolNotAllowedError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"ok: {run.ok}")
    typer.echo(f"output: {run.output}")
    typer.echo(f"outcome entry: {run.outcome_entry_id}")


@tools_app.command("promote")
def tools_promote(
    tool_id: Annotated[str, typer.Argument(help="Tool id to promote.")],
    data_dir: DataDirOpt = None,
) -> None:
    """Promote a candidate tool to 'promoted' so it can run freely (spec §4.4.6)."""
    registry = ToolRegistry(data_dir)
    if registry.get(tool_id) is None:
        typer.echo(f"no registered tool {tool_id!r}", err=True)
        raise typer.Exit(code=1)
    registry.set_status(tool_id, "promoted")
    store = MemoryStore(data_dir)
    loaded = store.latest_version(tool_id)
    if loaded is not None:
        loaded.entry.status = "promoted"  # type: ignore[assignment]
        store.write(loaded.entry, loaded.body)
    typer.echo(f"promoted {tool_id!r}")


@app.command("support")
def support(
    payload_file: Annotated[
        Path, typer.Argument(help="JSON payload for a coding_support action.")
    ],
    data_dir: DataDirOpt = None,
) -> None:
    """Run the Coding Support Loop from a JSON payload (spec §4.3)."""
    payload = json.loads(Path(payload_file).read_text(encoding="utf-8"))
    store = MemoryStore(data_dir)
    orch = Orchestrator(store)
    orch.register(CodingSupportLoop(store, context_provider=orch))
    task = Task(
        id=str(payload.get("id", "support-task")),
        kind="coding_support",
        payload=payload,
    )
    result = orch.dispatch(task)
    typer.echo(f"status: {result.status}")
    typer.echo(result.outcome_summary)
    if result.artifacts:
        typer.echo(f"artifacts: {', '.join(result.artifacts)}")


@app.command()
def metrics(data_dir: DataDirOpt = None) -> None:
    """Show value metrics derived from recorded data (spec §8)."""
    store = MemoryStore(data_dir)
    snapshot = compute_metrics(store, MetricsStore(store.data_dir).load())
    width = max(len(k) for k in snapshot)
    for key, value in snapshot.items():
        typer.echo(f"{key.ljust(width)} : {value}")


@app.command()
def doctor(
    fix: Annotated[bool, typer.Option(help="Recreate missing files from a stub.")] = False,
    root: Annotated[Path | None, typer.Option(help="Project root to check.")] = None,
) -> None:
    """Check the sacred continuity files exist (spec §7)."""
    guard = ContinuityGuard(root or Path.cwd())
    if fix:
        report = guard.recreate_missing()
        if report.recreated:
            typer.echo(f"recreated: {', '.join(report.recreated)}")
        else:
            typer.echo("all continuity files present")
        return
    missing = guard.check()
    if not missing:
        typer.echo("OK: all continuity files present")
        return
    typer.echo(f"MISSING: {', '.join(missing)}", err=True)
    raise typer.Exit(code=1)


@app.command("session-start")
def session_start(data_dir: DataDirOpt = None) -> None:
    """Begin a session: verify continuity and record recovery if memory exists."""
    guard = ContinuityGuard(Path.cwd())
    missing = guard.check()
    if missing:
        typer.echo(f"WARNING missing continuity files: {', '.join(missing)}", err=True)
    store = MemoryStore(data_dir)
    orch = Orchestrator(store)
    if store.iter_files():
        orch.record_recovery()
        typer.echo("recovery event recorded (memory contains prior entries)")
    else:
        typer.echo("fresh start (no prior memory entries)")


if __name__ == "__main__":
    app()
