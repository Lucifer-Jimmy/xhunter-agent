"""Waterfall tool middleware with a sandbox-only terminal executor."""

from collections.abc import Sequence

from xhunter.contracts.tool import Tool, ToolMiddleware, ToolRequest, ToolResult


class ToolDispatcher:
    def __init__(
        self,
        tools: dict[str, Tool],
        middleware: Sequence[ToolMiddleware] = (),
    ) -> None:
        self._tools = tools
        self._middleware = tuple(middleware)

    async def dispatch(self, request: ToolRequest) -> ToolResult:
        async def execute(request: ToolRequest) -> ToolResult:
            tool = self._tools.get(request.capability)
            if tool is None:
                return ToolResult.rejected_result(
                    f"no tool registered for capability: {request.capability}"
                )
            return await tool.execute(request)

        async def step(index: int, request: ToolRequest) -> ToolResult:
            if index == len(self._middleware):
                return await execute(request)
            return await self._middleware[index](
                request,
                lambda next_request: step(index + 1, next_request),
            )

        return await step(0, request)
