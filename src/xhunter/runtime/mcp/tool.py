"""Adapt an MCP server tool to xhunter's Tool contract."""

from xhunter.contracts.mcp import McpServerSpec, McpToolSpec, McpTransport
from xhunter.contracts.tool import ToolRequest, ToolResult


class McpTool:
    def __init__(
        self,
        server: McpServerSpec,
        spec: McpToolSpec,
        transport: McpTransport,
    ) -> None:
        if spec.server_id != server.server_id:
            raise ValueError("MCP tool and server ids must match")
        self._server = server
        self._spec = spec
        self._transport = transport
        self.capability = spec.capability

    async def execute(self, request: ToolRequest) -> ToolResult:
        result = await self._transport.call_tool(
            self._server, self._spec.name, request.arguments
        )
        return ToolResult(
            ok=not result.is_error,
            output=result.content if not result.is_error else "",
            error=result.content if result.is_error else None,
        )
