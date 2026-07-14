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
from loom_core.mcp.client import MCPClient, MCPConfig
from loom_core.mcp.installer import (
    Catalog,
    add_server,
    install_catalog,
    list_servers,
    remove_server,
)
from loom_core.metrics import MetricsStore, compute_metrics
from loom_core.models import parse_entry
from loom_core.models_config import DEFAULT_PROVIDERS, ModelStore
from loom_core.orchestrator import Orchestrator
from loom_core.plugins import install_plugin, list_plugins, remove_plugin
from loom_core.projects import (
    CONTINUITY_FILES,
    ProjectRegistry,
)
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

project_app = typer.Typer(help="Create, list and switch projects.")
app.add_typer(project_app, name="project")

models_app = typer.Typer(help="Configure LLM providers (spec §9).")
app.add_typer(models_app, name="models")

mcp_app = typer.Typer(help="Manage MCP servers (spec §13).")
app.add_typer(mcp_app, name="mcp")

plugin_app = typer.Typer(help="Manage Loom plugins (spec §13).")
app.add_typer(plugin_app, name="plugin")


@app.callback()
def main() -> None:
    """Loom Core - local-first, memory-centric runtime."""


@app.command()
def version() -> None:
    """Print the Loom Core version."""
    typer.echo(__version__)


def _load_json(payload_file: Path) -> dict[str, object]:
    """Read a JSON payload file, tolerating a UTF-8 BOM (e.g. from PowerShell)."""
    text = Path(payload_file).read_text(encoding="utf-8-sig")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise typer.BadParameter("payload JSON must be an object")
    return data


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
    payload = _load_json(payload_file)
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
    payload = _load_json(payload_file)
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
        _load_json(payload_file)
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


@app.command("fetch")
def web_fetch(
    url: Annotated[str, typer.Argument(help="URL to fetch.")],
    allow_untrusted: Annotated[
        bool, typer.Option(help="Bypass domain allowlist.")
    ] = False,
    data_dir: DataDirOpt = None,
) -> None:
    """Fetch a web page and extract text (spec §12)."""
    from loom_core.browser import WebBrowser

    browser = WebBrowser()
    try:
        result = browser.fetch(url, allow_untrusted=allow_untrusted)
    except PermissionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"url:    {result['url']}")
    typer.echo(f"status: {result['status']}")
    typer.echo(f"ok:     {result['ok']}")
    typer.echo(f"length: {result['length']}")
    if result["error"]:
        typer.echo(f"error:  {result['error']}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"\n{result['text']}")


# --- project commands (§6) --------------------------------------------------

_STUB_HEADER = (
    "# {name}\n\n"
    "> Generated by `loom project init {name}`.\n"
    "> This file belongs to the Loom continuity protocol (spec §5).\n\n"
)


@project_app.command("init")
def project_init(
    name: Annotated[str, typer.Argument(help="Project name.")],
    path: Annotated[
        Path | None, typer.Option(help="Project root directory (default: cwd/<name>).")
    ] = None,
    scaffold: Annotated[
        bool, typer.Option(help="Create per-project continuity file stubs.")
    ] = True,
) -> None:
    """Create a new Loom project with its own memory scope (§6)."""
    root = path or Path.cwd() / name
    if root.exists() and any(root.iterdir()):
        typer.echo(f"directory {root} already exists and is not empty", err=True)
        raise typer.Exit(code=1)
    root.mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(exist_ok=True)

    reg = ProjectRegistry()
    if reg.get(name) is not None:
        typer.echo(f"project {name!r} is already registered", err=True)
        raise typer.Exit(code=1)
    reg.register(name, str(root))

    if scaffold:
        for rel in CONTINUITY_FILES:
            target = root / rel
            if not target.exists():
                target.write_text(
                    _STUB_HEADER.format(name=name),
                    encoding="utf-8",
                    newline="\n",
                )

    reg.set_active(name)
    typer.echo(f"created project {name!r} at {root}")
    if scaffold:
        typer.echo(f"scaffolded continuity files: {', '.join(CONTINUITY_FILES)}")


@project_app.command("list")
def project_list() -> None:
    """List all registered projects (§6)."""
    reg = ProjectRegistry()
    projects = reg.list()
    if not projects:
        typer.echo("(no projects registered)")
        return
    active_name = reg.active_name()
    for p in projects:
        mark = "*" if p.name == active_name else " "
        typer.echo(f" {mark} {p.name}  ({p.path})")


@project_app.command("use")
def project_use(
    name: Annotated[str, typer.Argument(help="Project name to switch to.")],
) -> None:
    """Switch the active project; subsequent commands use its memory (§6)."""
    reg = ProjectRegistry()
    if reg.get(name) is None:
        typer.echo(f"unknown project {name!r}; use 'loom project init' first", err=True)
        raise typer.Exit(code=1)
    reg.set_active(name)
    typer.echo(f"active project: {name}")


@project_app.command("show")
def project_show(
    name: Annotated[str | None, typer.Argument(help="Project name (default: active).")] = None,
) -> None:
    """Show details about a project (§6)."""
    reg = ProjectRegistry()
    target = name or reg.active_name()
    if target is None:
        typer.echo("no active project (use 'loom project use <name>')", err=True)
        raise typer.Exit(code=1)
    proj = reg.get(target)
    if proj is None:
        typer.echo(f"unknown project {target!r}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"name:         {proj.name}")
    typer.echo(f"path:         {proj.path}")
    typer.echo(f"data dir:     {Path(proj.path) / 'data'}")
    typer.echo(f"created:      {proj.created}")
    typer.echo(f"last active:  {proj.last_active}")


# --- models commands (§9) ---------------------------------------------------


@models_app.command("add")
def models_add(
    name: Annotated[str, typer.Argument(help="Provider name.")],
    base_url: Annotated[str | None, typer.Option(help="API base URL.")] = None,
    api_key_env: Annotated[
        str | None, typer.Option(help="Env var holding the API key (never the key itself).")
    ] = None,
    default_model: Annotated[
        str | None, typer.Option(help="Default model for this provider.")
    ] = None,
) -> None:
    """Add or update an LLM provider (spec §9)."""
    defaults = DEFAULT_PROVIDERS.get(name.lower(), {})
    store = ModelStore()
    prov = store.add_provider(
        name=name,
        base_url=base_url or defaults.get("base_url", ""),
        api_key_env=api_key_env or defaults.get("api_key_env", ""),
        default_model=default_model or defaults.get("default_model", ""),
    )
    typer.echo(f"provider {name!r} configured (key env: {prov.api_key_env or 'none'})")


@models_app.command("list")
def models_list() -> None:
    """List configured LLM providers (§9)."""
    store = ModelStore()
    providers = store.list_providers()
    if not providers:
        typer.echo("(no providers configured; use 'loom models add <name>')")
        return
    active = store.active_provider_name()
    for p in providers:
        mark = "*" if p.name == active else " "
        typer.echo(
            f" {mark} {p.name}  model={p.default_model or '-'}  enum={p.api_key_env or '-'}"
        )


@models_app.command("use")
def models_use(
    name: Annotated[str, typer.Argument(help="Provider name to activate.")],
) -> None:
    """Set the active LLM provider (§9)."""
    store = ModelStore()
    if store.get_provider(name) is None:
        typer.echo(
            f"unknown provider {name!r}; use 'loom models add {name}' first", err=True
        )
        raise typer.Exit(code=1)
    store.set_active(name)
    active = store.active_provider()
    model = active.default_model if active is not None else "-"
    status = "configured" if store.is_configured() else "key not set"
    typer.echo(f"active provider: {name}  model={model}  ({status})")


# --- MCP commands (§13) ---------------------------------------------------


@mcp_app.command("install")
def mcp_install(
    name: Annotated[str, typer.Argument(help="Catalog entry name to install.")],
) -> None:
    """Install an MCP server from the catalog (one step, Hermes-style)."""
    try:
        cfg = install_catalog(name)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"installed {name!r} ({cfg.command} {' '.join(cfg.args)})")
    manifest = Catalog().get(name)
    if manifest and manifest.post_install:
        typer.echo(f"\n{manifest.post_install}")


@mcp_app.command("add")
def mcp_add(
    name: Annotated[str, typer.Argument(help="Server name.")],
    command: Annotated[str, typer.Option("--cmd", "-c", help="Command to run.")] = "",
    args: Annotated[
        list[str], typer.Option("--arg", "-a", help="Arguments (repeatable).")
    ] = [],  # noqa: B006
) -> None:
    """Add a custom MCP server (not from catalog)."""
    try:
        add_server(name, command, list(args))
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"added custom server {name!r}")


@mcp_app.command("list")
def mcp_list() -> None:
    """List installed MCP servers + catalog entries."""
    catalog = Catalog()
    installed = {s.name for s in list_servers()}

    if installed:
        typer.echo("--- Installed ---")
        for s in list_servers():
            typer.echo(f"  {s.name}  {s.command} {' '.join(s.args)}")
    else:
        typer.echo("(no servers installed)")

    typer.echo("\n--- Catalog ---")
    for m in catalog.list():
        mark = " [installed]" if m.name in installed else ""
        typer.echo(f"  {m.name}{mark}  {m.description}")


@mcp_app.command("remove")
def mcp_remove(name: Annotated[str, typer.Argument(help="Server name.")]) -> None:
    """Remove an installed MCP server."""
    if remove_server(name):
        typer.echo(f"removed {name!r}")
    else:
        typer.echo(f"unknown server {name!r}", err=True)
        raise typer.Exit(code=1)


@mcp_app.command("tools")
def mcp_tools(
    name: Annotated[str, typer.Argument(help="Server name.")],
) -> None:
    """Discover and list tools from an installed MCP server."""
    servers = list_servers()
    match = next((s for s in servers if s.name == name), None)
    if match is None:
        typer.echo(f"server {name!r} is not installed", err=True)
        raise typer.Exit(code=1)
    client = MCPClient(
        MCPConfig(command=match.command, args=match.args, env=match.env)
    )
    try:
        info = client.start()
        typer.echo(f"connected to {info.name} v{info.version}")
        for t in client.discover_tools():
            typer.echo(f"  {t.name}  {t.description}")
    except Exception as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        client.stop()


# --- plugin commands (§13) --------------------------------------------------


@plugin_app.command("install")
def plugin_install(
    spec: Annotated[str, typer.Argument(help="owner/repo shorthand, or full Git URL.")],
) -> None:
    """Install a plugin from GitHub (one step, Hermes-style)."""
    try:
        info = install_plugin(spec)
    except FileExistsError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"installed plugin {info.name!r} at {info.path}")


@plugin_app.command("list")
def plugin_list() -> None:
    """List installed plugins."""
    plugins = list_plugins()
    if not plugins:
        typer.echo("(no plugins installed)")
        return
    for p in plugins:
        typer.echo(f"  {p.name}  {p.path}")


@plugin_app.command("remove")
def plugin_remove(
    name: Annotated[str, typer.Argument(help="Plugin name to remove.")],
) -> None:
    """Remove an installed plugin."""
    if remove_plugin(name):
        typer.echo(f"removed {name!r}")
    else:
        typer.echo(f"unknown plugin {name!r}", err=True)
        raise typer.Exit(code=1)


@app.command("support")
def support(
    payload_file: Annotated[
        Path, typer.Argument(help="JSON payload for a coding_support action.")
    ],
    data_dir: DataDirOpt = None,
) -> None:
    """Run the Coding Support Loop from a JSON payload (spec §4.3)."""
    payload = _load_json(payload_file)
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
def value(data_dir: DataDirOpt = None) -> None:
    """Show value metrics (alias for metrics, spec §15)."""
    _show_metrics(data_dir)


@app.command()
def stats(data_dir: DataDirOpt = None) -> None:
    """Show metrics (alias for metrics, spec §15)."""
    _show_metrics(data_dir)


@app.command()
def metrics(data_dir: DataDirOpt = None) -> None:
    """Show value metrics derived from recorded data (spec §15)."""
    _show_metrics(data_dir)


def _show_metrics(data_dir: Path | None = None) -> None:
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


@app.command()
def tui(data_dir: DataDirOpt = None) -> None:
    """Launch the Loom Core Terminal UI (spec §11)."""
    from loom_core.tui.app import LoomApp

    app = LoomApp(data_dir=str(data_dir) if data_dir else None)
    app.run()


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
