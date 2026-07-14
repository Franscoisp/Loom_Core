"""Loom MCP client package (§13) — simple Hermes-style UX."""
from loom_core.mcp.installer import (
    Catalog,
    ServerConfig,
    add_server,
    install_catalog,
    list_servers,
    remove_server,
)

__all__ = [
    "Catalog",
    "ServerConfig",
    "add_server",
    "install_catalog",
    "list_servers",
    "remove_server",
]
