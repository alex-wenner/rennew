import asyncio
import itertools
import json
from typing import Any

from pydantic import BaseModel

from rennew.providers.contracts import ToolSchema

MCP_PROTOCOL_VERSION = "2025-06-18"


class MCPServerConfig(BaseModel):
    name: str
    command: str
    args: list[str] = []
    env: dict[str, str] = {}


class MCPServerConnection:
    """A live stdio connection to one MCP server."""

    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self._process: asyncio.subprocess.Process | None = None
        self._request_ids = itertools.count(1)
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._closed = False

    async def connect(self, timeout: float = 15.0) -> None:
        import os

        env = {**os.environ, **self.config.env}
        self._process = await asyncio.create_subprocess_exec(
            self.config.command,
            *self.config.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=env,
        )
        self._reader_task = asyncio.create_task(self._read_loop())
        initialize_result = await asyncio.wait_for(
            self._request(
                "initialize",
                {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "rennew", "version": "0.1.0"},
                },
            ),
            timeout=timeout,
        )
        _ = initialize_result
        await self._notify("notifications/initialized", {})

    async def _read_loop(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        while True:
            line = await self._process.stdout.readline()
            if not line:
                break
            try:
                message = json.loads(line.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue
            message_id = message.get("id")
            if isinstance(message_id, int) and message_id in self._pending:
                future = self._pending.pop(message_id)
                if not future.done():
                    future.set_result(message)

    async def _send(self, payload: dict[str, Any]) -> None:
        assert self._process is not None and self._process.stdin is not None
        data = (json.dumps(payload) + "\n").encode("utf-8")
        self._process.stdin.write(data)
        await self._process.stdin.drain()

    async def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = next(self._request_ids)
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        await self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        response = await future
        if "error" in response:
            raise RuntimeError(f"MCP error: {response['error']}")
        return response.get("result") or {}

    async def _notify(self, method: str, params: dict[str, Any]) -> None:
        await self._send({"jsonrpc": "2.0", "method": method, "params": params})

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._request("tools/list", {})
        tools = result.get("tools")
        return tools if isinstance(tools, list) else []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        result = await self._request("tools/call", {"name": name, "arguments": arguments})
        content = result.get("content")
        parts: list[str] = []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text") or ""))
        return "\n".join(parts) if parts else json.dumps(result)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._reader_task is not None:
            self._reader_task.cancel()
        if self._process is not None:
            try:
                self._process.terminate()
            except ProcessLookupError:
                pass
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()


class MCPManager:
    """Owns MCP server connections and exposes their tools with `mcp__<server>__<tool>` names."""

    def __init__(self) -> None:
        self._connections: dict[str, MCPServerConnection] = {}
        self._tool_index: dict[str, tuple[str, str]] = {}
        self._errors: dict[str, str] = {}

    async def connect(self, config: MCPServerConfig) -> None:
        connection = MCPServerConnection(config)
        try:
            await connection.connect()
        except Exception as error:  # noqa: BLE001 - surface per-server failures
            self._errors[config.name] = str(error)
            await connection.close()
            return
        self._connections[config.name] = connection
        for tool in await connection.list_tools():
            tool_name = str(tool.get("name") or "")
            if not tool_name:
                continue
            self._tool_index[f"mcp__{config.name}__{tool_name}"] = (config.name, tool_name)

    def status(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for name, connection in self._connections.items():
            rows.append({"name": name, "status": "connected", "command": connection.config.command})
        for name, error in self._errors.items():
            rows.append({"name": name, "status": "failed", "error": error})
        return rows

    def tool_schemas(self, all_tools: dict[str, dict[str, Any]] | None = None) -> list[ToolSchema]:
        schemas: list[ToolSchema] = []
        for qualified in sorted(self._tool_index):
            schemas.append(
                ToolSchema(
                    name=qualified,
                    description=f"MCP tool {qualified}.",
                    parameters={"type": "object", "properties": {}},
                )
            )
        return schemas

    async def call(self, qualified_name: str, arguments: dict[str, Any]) -> str:
        target = self._tool_index.get(qualified_name)
        if target is None:
            raise RuntimeError(f"Unknown MCP tool: {qualified_name}")
        server_name, tool_name = target
        connection = self._connections.get(server_name)
        if connection is None:
            raise RuntimeError(f"MCP server not connected: {server_name}")
        return await connection.call_tool(tool_name, arguments)

    def is_mcp_tool(self, name: str) -> bool:
        return name in self._tool_index

    async def close(self) -> None:
        for connection in self._connections.values():
            await connection.close()
        self._connections.clear()
        self._tool_index.clear()
