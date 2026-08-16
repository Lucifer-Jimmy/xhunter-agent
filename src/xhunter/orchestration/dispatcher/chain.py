"""Waterfall tool middleware with a sandbox-only terminal executor."""

from collections.abc import Callable, Mapping, Sequence

from xhunter.contracts.tool import Tool, ToolMiddleware, ToolRequest, ToolResult

ToolResolver = Callable[[str], Tool | None]


class ToolDispatcher:
    def __init__(
        self,
        tools: Mapping[str, Tool] | ToolResolver,
        middleware: Sequence[ToolMiddleware] = (),
    ) -> None:
        self._resolve = tools if callable(tools) else tools.get
        self._middleware = tuple(middleware)

    async def dispatch(self, request: ToolRequest) -> ToolResult:
        tool = self._resolve(request.capability)
        if tool is None:
            return ToolResult.rejected_result(
                f"no tool registered for capability: {request.capability}"
            )

        async def execute(request: ToolRequest) -> ToolResult:
            return await tool.execute(request)

        async def step(index: int, request: ToolRequest) -> ToolResult:
            if index == len(self._middleware):
                return await execute(request)
            return await self._middleware[index](
                request,
                lambda next_request: step(index + 1, next_request),
            )

        return await step(0, request)
