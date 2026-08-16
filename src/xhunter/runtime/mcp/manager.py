"""Discover MCP tools and register them with reversible lifecycle semantics."""

from collections.abc import Callable

from xhunter.contracts.mcp import McpServerSpec, McpTransport
from xhunter.runtime.capability import CapabilityRegistry
from xhunter.runtime.mcp.tool import McpTool


class McpServerManager:
    def __init__(
        self,
        registry: CapabilityRegistry,
        transport: McpTransport,
    ) -> None:
        self._registry = registry
        self._transport = transport
        self._disposers: list[Callable[[], None]] = []
        self._started = False

    async def start(self, server: McpServerSpec) -> tuple[str, ...]:
        if self._started:
            raise RuntimeError("MCP manager is already started")
        if not server.server_id or not server.command:
            raise ValueError("MCP server id and command must not be empty")

        tools = await self._transport.list_tools(server)
        capabilities: list[str] = []
        try:
            for spec in tools:
                tool = McpTool(server, spec, self._transport)
                self._disposers.append(self._registry.register(tool))
                capabilities.append(tool.capability)
        except Exception:
            self._dispose_tools()
            await self._transport.close()
            raise
        self._started = True
        return tuple(capabilities)

    async def stop(self) -> None:
        self._dispose_tools()
        await self._transport.close()
        self._started = False

    def _dispose_tools(self) -> None:
        while self._disposers:
            self._disposers.pop()()
