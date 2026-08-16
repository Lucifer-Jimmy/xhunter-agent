"""Deterministic MCP transport for contract and Agent integration tests."""

from collections.abc import Callable

from xhunter.contracts.mcp import (
    McpCallResult,
    McpServerSpec,
    McpToolSpec,
)


class FakeMcpTransport:
    def __init__(
        self,
        tools: tuple[McpToolSpec, ...],
        handler: Callable[[str, dict[str, object]], McpCallResult],
    ) -> None:
        self._tools = tools
        self._handler = handler
        self.calls: list[tuple[str, str, dict[str, object]]] = []
        self.closed = False

    async def list_tools(self, server: McpServerSpec) -> tuple[McpToolSpec, ...]:
        if self.closed:
            raise RuntimeError("MCP transport is closed")
        return self._tools

    async def call_tool(
        self,
        server: McpServerSpec,
        tool_name: str,
        arguments: dict[str, object],
    ) -> McpCallResult:
        if self.closed:
            raise RuntimeError("MCP transport is closed")
        self.calls.append((server.server_id, tool_name, arguments))
        return self._handler(tool_name, arguments)

    async def close(self) -> None:
        self.closed = True
