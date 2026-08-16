"""Standard stdio MCP requests executed entirely inside the Sandbox."""

import json

from xhunter.contracts.mcp import (
    McpCallResult,
    McpServerSpec,
    McpToolSpec,
)
from xhunter.contracts.sandbox import Sandbox, SandboxRequest

_BRIDGE = """
import asyncio
import json
import os
import sys

async def send(process, message):
    process.stdin.write((json.dumps(message, separators=(",", ":")) + "\\n").encode())
    await process.stdin.drain()

async def receive(process, request_id):
    while True:
        line = await process.stdout.readline()
        if not line:
            error = (await process.stderr.read()).decode(errors="replace")
            raise RuntimeError(f"MCP server closed before response: {error[:1000]}")
        message = json.loads(line)
        if message.get("id") == request_id:
            return message

async def main():
    envelope = json.load(sys.stdin)
    environment = {
        name: os.environ[name]
        for name in ("PATH", "HOME", "TMPDIR", "TEMP", "TMP")
        if name in os.environ
    }
    environment.update(envelope.get("environment", {}))
    process = await asyncio.create_subprocess_exec(
        *envelope["command"],
        cwd=envelope.get("working_directory"),
        env=environment,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        await send(process, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "xhunter", "version": "0.1.0"},
            },
        })
        initialized = await receive(process, 1)
        if "error" in initialized:
            raise RuntimeError(json.dumps(initialized["error"]))
        await send(process, {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        })
        await send(process, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": envelope["method"],
            "params": envelope.get("params", {}),
        })
        response = await receive(process, 2)
        print(json.dumps(response, separators=(",", ":")))
    finally:
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 2)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

asyncio.run(main())
""".strip()


class SandboxMcpTransport:
    def __init__(
        self,
        sandbox: Sandbox,
        executable: str = "python3",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._sandbox = sandbox
        self._executable = executable
        self._timeout_seconds = timeout_seconds

    async def list_tools(self, server: McpServerSpec) -> tuple[McpToolSpec, ...]:
        result = await self._request(server, "tools/list", {})
        tools = result.get("tools")
        if not isinstance(tools, list):
            raise RuntimeError("MCP tools/list result has no tools list")
        return tuple(_tool_spec(server.server_id, tool) for tool in tools)

    async def call_tool(
        self,
        server: McpServerSpec,
        tool_name: str,
        arguments: dict[str, object],
    ) -> McpCallResult:
        result = await self._request(
            server,
            "tools/call",
            {"name": tool_name, "arguments": arguments},
        )
        content = result.get("content", [])
        if not isinstance(content, list):
            raise RuntimeError("MCP tools/call content must be a list")
        text = "\n".join(_content_text(item) for item in content)
        return McpCallResult(text, bool(result.get("isError", False)))

    async def close(self) -> None:
        return None

    async def _request(
        self,
        server: McpServerSpec,
        method: str,
        params: dict[str, object],
    ) -> dict[str, object]:
        if not server.command:
            raise ValueError("MCP server command must not be empty")
        envelope = {
            "command": server.command,
            "environment": server.environment,
            "working_directory": server.working_directory,
            "method": method,
            "params": params,
        }
        execution = await self._sandbox.execute(
            SandboxRequest(
                (self._executable, "-I", "-c", _BRIDGE),
                stdin=json.dumps(envelope).encode(),
                timeout_seconds=self._timeout_seconds,
            )
        )
        if execution.exit_code != 0:
            detail = (execution.stderr or execution.stdout)[:1000]
            raise RuntimeError(
                f"Sandbox MCP bridge failed: {detail}"
            )
        try:
            response = json.loads(execution.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Sandbox MCP bridge returned invalid JSON") from exc
        if not isinstance(response, dict):
            raise RuntimeError("MCP response root must be an object")
        if "error" in response:
            raise RuntimeError(f"MCP request failed: {response['error']}")
        result = response.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("MCP response has no result object")
        return result


def _tool_spec(server_id: str, value: object) -> McpToolSpec:
    if not isinstance(value, dict):
        raise RuntimeError("MCP tool entry must be an object")
    name = value.get("name")
    description = value.get("description", "")
    schema = value.get("inputSchema", {"type": "object"})
    if not isinstance(name, str) or not isinstance(description, str):
        raise RuntimeError("MCP tool name and description must be strings")
    if not isinstance(schema, dict):
        raise RuntimeError("MCP tool inputSchema must be an object")
    return McpToolSpec(server_id, name, description, schema)


def _content_text(value: object) -> str:
    if not isinstance(value, dict):
        raise RuntimeError("MCP content entry must be an object")
    content_type = value.get("type")
    if content_type != "text" or not isinstance(value.get("text"), str):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    return value["text"]
