"""MCP: Model Context Protocol support (spec §13).

Simple, Hermes-style UX:
    loom mcp                       # interactive catalog picker
    loom mcp list                  # show catalog + installed servers
    loom mcp install <name>        # one-step catalog install
    loom mcp add <name> --command <cmd> --args ...  # custom server
    loom mcp remove <name>
    loom mcp tools <name>          # discover and list tools

Config lives in ``~/.loom/mcp_servers.yaml``. The MCP client transport
(mcp/client.py) handles the JSON-RPC protocol. This module handles the UX.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from typing import Any

import yaml

LOOM_HOME = Path.home() / ".loom"
CATALOG_DIR = Path(__file__).parent / "catalog"
SERVERS_CONFIG = LOOM_HOME / "mcp_servers.yaml"


@dataclass
class Manifest:
    name: str = ""
    description: str = ""
    transport: dict[str, Any] = field(default_factory=dict)
    install: dict[str, Any] | None = None
    auth: dict[str, Any] = field(default_factory=dict)
    post_install: str = ""


@dataclass
class ServerConfig:
    name: str = ""
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    installed: bool = False
    source: str = ""  # "catalog" | "custom"


class Catalog:
    """Loads MCP manifest YAML files from the catalog directory."""

    def __init__(self) -> None:
        self._entries: dict[str, Manifest] = {}

    def _load(self) -> dict[str, Manifest]:
        if self._entries:
            return self._entries
        if not CATALOG_DIR.exists():
            return {}
        for f in sorted(CATALOG_DIR.glob("*.yaml")):
            raw = yaml.safe_load(f.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or raw.get("name") is None:
                continue
            m = Manifest(
                name=raw.get("name", ""),
                description=raw.get("description", ""),
                transport=raw.get("transport", {}),
                install=raw.get("install"),
                auth=raw.get("auth", {}),
                post_install=raw.get("post_install", ""),
            )
            self._entries[m.name] = m
        return self._entries

    def list(self) -> list[Manifest]:
        return list(self._load().values())

    def get(self, name: str) -> Manifest | None:
        return self._load().get(name)


def _load_servers() -> dict[str, dict[str, Any]]:
    if not SERVERS_CONFIG.exists():
        return {}
    raw = yaml.safe_load(SERVERS_CONFIG.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    servers: dict[str, dict[str, Any]] = raw.get("mcp_servers", {})
    return servers


def _save_servers(data: dict[str, dict[str, Any]]) -> None:
    SERVERS_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    with open(SERVERS_CONFIG, "w", encoding="utf-8", newline="\n") as fh:
        yaml.safe_dump({"mcp_servers": data}, fh, sort_keys=False, allow_unicode=True)


def list_servers() -> list[ServerConfig]:
    """Return all installed MCP servers."""
    data = _load_servers()
    result: list[ServerConfig] = []
    for name in sorted(data):
        cfg = data[name]
        result.append(ServerConfig(
            name=name,
            command=str(cfg.get("command", "")),
            args=[str(a) for a in cfg.get("args", [])],
            env=dict(cfg.get("env", {})),
            installed=True,
            source=str(cfg.get("source", "custom")),
        ))
    return result


def install_catalog(name: str) -> ServerConfig:
    """Install a catalog entry by name. Handles git clone, bootstrap, secrets."""
    catalog = Catalog()
    manifest = catalog.get(name)
    if manifest is None:
        available = ", ".join(m.name for m in catalog.list())
        raise ValueError(f"unknown catalog entry {name!r}. Available: {available}")

    install_dir = LOOM_HOME / "mcp" / name

    # Git clone if needed
    install_cfg = manifest.install
    if install_cfg:
        repo_url = install_cfg.get("url", "")
        ref = install_cfg.get("ref", "main")
        if not install_dir.exists():
            subprocess.run(
                ["git", "clone", str(repo_url), str(install_dir)],
                check=True,
                capture_output=True,
            )
        else:
            subprocess.run(
                ["git", "fetch"], cwd=str(install_dir), check=True, capture_output=True
            )
        subprocess.run(
            ["git", "checkout", str(ref)],
            cwd=str(install_dir),
            check=True,
            capture_output=True,
        )
        for cmd in install_cfg.get("bootstrap", []):
            subprocess.run(
                shlex.split(str(cmd)), cwd=str(install_dir), check=True
            )

    # Substitute ${INSTALL_DIR} in command/args
    transport = manifest.transport
    cmd = str(transport.get("command", "")).replace(
        "${INSTALL_DIR}", str(install_dir)
    )
    args_raw: list[object] = transport.get("args", [])
    args: list[str] = [
        str(a).replace("${INSTALL_DIR}", str(install_dir)) for a in args_raw
    ]
    args = [
        os.path.expandvars(Template(a).safe_substitute(os.environ)) for a in args
    ]

    # Collect env vars
    env: dict[str, str] = {}
    auth = manifest.auth
    for env_cfg in auth.get("env", []):
        key = str(env_cfg.get("name", ""))
        if not key:
            continue
        # In a real interactive TUI/CLI, we'd prompt the user.
        # For now, read from environment or use default.
        default = str(env_cfg.get("default", ""))
        env[key] = os.environ.get(key, default)

    # Save to config
    data = _load_servers()
    data[name] = {
        "command": cmd,
        "args": args,
        "env": env,
        "source": "catalog",
    }
    _save_servers(data)

    return ServerConfig(
        name=name, command=cmd, args=args, env=env,
        installed=True, source="catalog",
    )


def add_server(name: str, command: str, args: list[str] | None = None,
               env: dict[str, str] | None = None) -> ServerConfig:
    """Add a custom MCP server (not from catalog)."""
    data = _load_servers()
    if name in data:
        raise ValueError(f"server {name!r} already exists. Use 'loom mcp remove {name}' first.")
    data[name] = {
        "command": command,
        "args": args or [],
        "env": env or {},
        "source": "custom",
    }
    _save_servers(data)
    return ServerConfig(
        name=name, command=command, args=args or [], env=env or {},
        installed=True, source="custom",
    )


def remove_server(name: str) -> bool:
    data = _load_servers()
    if name not in data:
        return False
    del data[name]
    _save_servers(data)
    return True
