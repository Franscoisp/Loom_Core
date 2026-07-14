"""MCP protocol types (JSON-RPC 2.0 over stdio/SSE).

The Model Context Protocol (MCP) uses JSON-RPC 2.0 with newline-delimited
messages over stdio, or Server-Sent Events over HTTP. This module defines the
core types and a stdio transport. No external deps.
"""

from __future__ import annotations

import json
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MCPTool:
    """An MCP tool discovered from a server."""
    name: str
    description: str = ""
    input_schema: dict[str, object] = field(default_factory=dict)


@dataclass
class MCPServerInfo:
    name: str = ""
    version: str = ""


@dataclass
class MCPConfig:
    """How to launch an MCP server."""
    command: str  # e.g. "python" or "npx"
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    server_name: str = ""
    server_version: str = ""


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------

_next_id: int = 0
_id_lock = threading.Lock()


def _new_id() -> int:
    global _next_id
    with _id_lock:
        _next_id += 1
        return _next_id


def _rpc_request(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": _new_id(),
        "method": method,
        "params": params or {},
    }


# ---------------------------------------------------------------------------
# MCP stdio client
# ---------------------------------------------------------------------------


class MCPError(RuntimeError):
    pass


class MCPClient:
    """A lightweight MCP client that spawns a server over stdio (spec §13)."""

    def __init__(self, config: MCPConfig, timeout: float = 30.0) -> None:
        self.config = config
        self.timeout = timeout
        self._proc: subprocess.Popen[bytes] | None = None
        self._server_info: MCPServerInfo = MCPServerInfo()
        self._tools: list[MCPTool] = []
        self._pending: dict[int, threading.Event] = {}
        self._responses: dict[int, dict[str, Any]] = {}
        self._reader_thread: threading.Thread | None = None
        self._running = False

    def start(self) -> MCPServerInfo:
        cmd = [self.config.command, *self.config.args]
        env = {**__import__("os").environ, **self.config.env}

        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        self._running = True
        self._reader_thread = threading.Thread(target=self._reader, daemon=True)
        self._reader_thread.start()

        result = self._call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "LoomCore", "version": "0.0.1"},
        })
        info = result.get("serverInfo", {})
        self._server_info = MCPServerInfo(
            name=info.get("name", ""), version=info.get("version", "")
        )

        # Send initialized notification
        self._send_notification("notifications/initialized", {})
        return self._server_info

    def stop(self) -> None:
        self._running = False
        if self._proc and self._proc.stdin:
            self._proc.stdin.close()
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None

    @property
    def server_info(self) -> MCPServerInfo:
        return self._server_info

    def discover_tools(self) -> list[MCPTool]:
        result = self._call("tools/list", {})
        self._tools = [
            MCPTool(
                name=t.get("name", ""),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
            )
            for t in result.get("tools", [])
        ]
        return self._tools

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self._call("tools/call", {
            "name": name,
            "arguments": arguments or {},
        })
        content = result.get("content", [])
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        return {
            "result": result,
            "text": "\n".join(texts),
            "is_error": result.get("isError", False),
        }

    # --- internal -----------------------------------------------------------

    def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        req = _rpc_request(method, params)
        rid = req["id"]
        event = threading.Event()
        self._pending[rid] = event
        self._send(req)
        if not event.wait(self.timeout):
            raise MCPError(f"timeout waiting for {method}")
        resp: dict[str, Any] = self._responses.pop(rid, {})
        if "error" in resp:
            err = resp["error"]
            raise MCPError(f"MCP error {method}: {err.get('message', err)}")
        result = resp.get("result", {})
        assert isinstance(result, dict)
        return result

    def _send(self, msg: dict[str, Any]) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise MCPError("MCP server not started")
        line = json.dumps(msg, ensure_ascii=False) + "\n"
        self._proc.stdin.write(line.encode("utf-8"))
        self._proc.stdin.flush()

    def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _reader(self) -> None:
        assert self._proc and self._proc.stdout
        for line in self._proc.stdout:
            if not self._running:
                break
            line_str = line.decode("utf-8", errors="replace").strip()
            if not line_str:
                continue
            try:
                msg = json.loads(line_str)
            except json.JSONDecodeError:
                continue
            rid = msg.get("id")
            if rid is not None and rid in self._pending:
                self._responses[rid] = msg
                self._pending[rid].set()
