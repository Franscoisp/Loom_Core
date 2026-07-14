"""Loom TUI — Textual-based terminal interface (spec §11).

Architecture inspired by Hermes TUI patterns (view navigation, status bar,
slash commands, modal details) but built with Python/Textual per the Loom v3.0
spec instead of React/Ink. Clean separation from core logic.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import (
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

from loom_core.metrics import MetricsStore, compute_metrics
from loom_core.models import BaseEntry, EntryType
from loom_core.orchestrator import Orchestrator
from loom_core.projects import ProjectRegistry
from loom_core.store import MemoryStore


class _StatusBar(Static):
    """Top status bar: phase, active model, ownership claims, quick value."""

    def render(self) -> str:
        app = self.app
        if not isinstance(app, LoomApp):
            return ""
        phase = app.status_phase
        model = app.status_model
        claims = app.status_claims
        value = app.status_value
        return (
            f" phase: {phase} │ model: {model} │ claims: {claims} │ {value}"
        )


class _Sidebar(ListView):
    """Toggleable left sidebar for view navigation."""

    BINDINGS = [
        Binding("ctrl+b", "toggle_sidebar", "Toggle sidebar", show=False),
    ]

    def on_mount(self) -> None:
        nav = [" Chat", " Memory", " Skills", " Progress", " Value", " Loops"]
        for label in nav:
            self.append(ListItem(Label(label)))


class MemoryView(Vertical):
    """Browse memory entries by layer, with filtering."""

    def compose(self) -> ComposeResult:
        yield Static("--- Memory Browser ---", id="view-title")
        yield Static("Select a layer below:", id="memory-hint")
        layers = [
            ("All", ""),
            ("Core", EntryType.core.value),
            ("Episodic", EntryType.episode.value),
            ("Skills", EntryType.skill.value),
            ("Tools", EntryType.tool.value),
            ("Anti-Patterns", EntryType.anti_pattern.value),
            ("Entities", EntryType.entity.value),
        ]
        for label, _etype in layers:
            yield ListItem(Label(f" {label}"))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = event.item_index if hasattr(event, "item_index") else 0
        layers = ["", "core", "episode", "skill", "tool", "anti-pattern", "entity"]
        etype = layers[idx] if idx < len(layers) else ""
        app = self.app
        if not isinstance(app, LoomApp):
            return
        store = MemoryStore(app.current_data_dir)
        entries = store.list_entries(type=etype or None)
        result = self.query_one("#memory-list", Static)
        if not entries:
            result.update("(no matching entries)")
            return
        lines = []
        for i, loaded in enumerate(entries):
            e = loaded.entry
            marker = ">" if i == 0 else " "
            lines.append(
                f"{marker} [{e.type}] {e.title}  status={e.status}  "
                f"id={e.id}"
            )
        result.update("\n".join(lines))


class SkillsView(Vertical):
    """List skills with success rates."""

    def compose(self) -> ComposeResult:
        yield Static("--- Skills ---", id="view-title")
        yield Static("Loading...", id="skills-list")

    def on_mount(self) -> None:
        app = self.app
        if not isinstance(app, LoomApp):
            return
        store = MemoryStore(app.current_data_dir)
        entries = store.list_entries(type=EntryType.skill.value)
        latest: dict[str, BaseEntry] = {}
        for loaded in entries:
            e = loaded.entry
            v = int(getattr(e, "version", 1))
            if e.id not in latest or v > int(getattr(latest[e.id], "version", 1)):
                latest[e.id] = e
        lines = []
        for e in latest.values():
            lines.append(
                f"- {e.id}  v{getattr(e, 'version', 1)}  "
                f"rate={getattr(e, 'success_rate', 0):.2f}  "
                f"[{getattr(e, 'status', '?')}]"
            )
        self.query_one("#skills-list", Static).update(
            "\n".join(lines) if lines else "(no skills found)"
        )


class ValueView(Vertical):
    """Show value metrics (§15)."""

    def compose(self) -> ComposeResult:
        yield Static("--- Value & Metrics ---", id="view-title")
        yield Static("Loading...", id="value-list")

    def on_mount(self) -> None:
        app = self.app
        if not isinstance(app, LoomApp):
            return
        store = MemoryStore(app.current_data_dir)
        m = compute_metrics(store, MetricsStore(store.data_dir).load())
        lines = [f"{k} : {v}" for k, v in m.items()]
        self.query_one("#value-list", Static).update("\n".join(lines))


class ProgressView(Vertical):
    """Show continuity file content (PROGRESS.md, TASKS.md)."""

    def compose(self) -> ComposeResult:
        yield Static("--- Progress ---", id="view-title")
        yield Static("Loading...", id="progress-content")

    def on_mount(self) -> None:
        content = ""
        for name in ("PROGRESS.md", "CURRENT_FOCUS.md"):
            p = Path(name)
            if p.exists():
                content += f"\n## {name}\n\n"
                text = p.read_text(encoding="utf-8")
                content += text[:2000] + ("\n\n... (truncated)" if len(text) > 2000 else "")
        self.query_one("#progress-content", Static).update(content or "(no continuity files found)")


class LoopsView(Vertical):
    """Show registered loops and ownership status."""

    def compose(self) -> ComposeResult:
        yield Static("--- Loops ---", id="view-title")
        yield Static("Loading...", id="loops-list")

    def on_mount(self) -> None:
        app = self.app
        if not isinstance(app, LoomApp):
            return
        orch = Orchestrator(MemoryStore(app.current_data_dir))
        lines = [f"- {loop.name} (can_handle: registered)" for loop in orch.loops]
        self.query_one("#loops-list", Static).update(
            "\n".join(lines) if lines else "(no loops registered)"
        )


class ChatView(Vertical):
    """Chat/command input view."""

    def compose(self) -> ComposeResult:
        yield Static("--- Loom Core ---", id="view-title")
        yield Static(
            "Type commands or use the sidebar to navigate. "
            "/help for commands, /quit to exit.",
            id="chat-output",
        )
        yield Input(placeholder="> ", id="chat-input")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value:
            return
        output = self.query_one("#chat-output", Static)

        if value.startswith("/"):
            cmd = value[1:].split()[0]
            if cmd == "quit" or cmd == "exit":
                self.app.exit()
                return
            if cmd == "help":
                output.update(
                    "Commands:\n"
                    "  /help      show this help\n"
                    "  /quit      exit the TUI\n"
                    "  /refresh   reload current view\n"
                )
                return
            if cmd == "refresh":
                output.update(f"Refreshing... (command: {value})")
                return
            output.update(f"Unknown command: {value!r}\nTry /help")
            return

        output.update(f"> {value}\n\nResult not available in TUI. Use CLI for this command.")


class LoomApp(App):  # type: ignore[type-arg]
    """Loom Core Terminal UI (spec §11)."""

    CSS = """
    Screen {
        layout: horizontal;
    }
    _Sidebar {
        width: 20;
        height: 100%;
        border: solid $primary;
        margin: 0 1 0 0;
        display: none;
    }
    _Sidebar.-visible {
        display: block;
    }
    _StatusBar {
        dock: top;
        height: 1;
        background: $primary;
        color: $text;
    }
    #view-container {
        width: 1fr;
        height: 100%;
    }
    #view-title {
        height: 1;
        text-style: bold;
        background: $primary-darken-2;
        padding: 0 1;
    }
    #chat-input {
        dock: bottom;
        margin: 1 0 0 0;
    }
    View {
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+b", "toggle_sidebar", "Sidebar", show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("1", "view_chat", "Chat"),
        Binding("2", "view_memory", "Memory"),
        Binding("3", "view_skills", "Skills"),
        Binding("4", "view_progress", "Progress"),
        Binding("5", "view_value", "Value"),
        Binding("6", "view_loops", "Loops"),
    ]

    status_phase: str = "v3.0"
    status_model: str = "-"
    status_claims: int = 0
    status_value: str = "-"

    def __init__(self, data_dir: str | None = None) -> None:
        super().__init__()
        self.current_data_dir = data_dir or "data"

    def compose(self) -> ComposeResult:
        yield _StatusBar()
        yield _Sidebar(classes="-visible")
        with Container(id="view-container"):
            yield ChatView()

    def on_mount(self) -> None:
        self._refresh_status()
        reg = ProjectRegistry()
        active = reg.active()
        if active is not None:
            self.current_data_dir = str(Path(active.path) / "data")
        store = MemoryStore(self.current_data_dir)
        if store.iter_files():
            m = compute_metrics(store, MetricsStore(store.data_dir).load())
            self.status_value = (
                f"decisions={m.get('decisions_preserved', 0)} "
                f"skills={m.get('skills_created', 0)} "
                f"runs={m.get('distillation_runs', 0)}"
            )
            self.status_phase = "v3.0"
        self.query_one(_StatusBar).refresh()

    def _refresh_status(self) -> None:
        self.query_one(_StatusBar).refresh()

    def action_toggle_sidebar(self) -> None:
        sidebar = self.query_one(_Sidebar)
        sidebar.toggle_class("-visible")

    def _switch_view(self, view_cls: type[Vertical]) -> None:
        container = self.query_one("#view-container", Container)
        for child in list(container.children):
            child.remove()
        container.mount(view_cls())

    def action_view_chat(self) -> None:
        self._switch_view(ChatView)

    def action_view_memory(self) -> None:
        container = self.query_one("#view-container", Container)
        for child in list(container.children):
            child.remove()
        container.mount(MemoryView())

    def action_view_skills(self) -> None:
        self._switch_view(SkillsView)

    def action_view_progress(self) -> None:
        self._switch_view(ProgressView)

    def action_view_value(self) -> None:
        self._switch_view(ValueView)

    def action_view_loops(self) -> None:
        self._switch_view(LoopsView)
