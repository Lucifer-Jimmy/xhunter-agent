"""Reversible capability registration."""

from collections.abc import Callable

from xhunter.contracts.tool import Tool, ToolSpec


class CapabilityRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> Callable[[], None]:
        capability = tool.capability
        tool.spec.validate()
        if tool.spec.capability != capability:
            raise ValueError("tool spec capability does not match tool capability")
        if not capability:
            raise ValueError("tool capability must not be empty")
        if capability in self._tools:
            raise ValueError(f"capability already registered: {capability}")
        self._tools[capability] = tool

        def dispose() -> None:
            if self._tools.get(capability) is tool:
                del self._tools[capability]

        return dispose

    def resolve(self, capability: str) -> Tool | None:
        return self._tools.get(capability)

    def snapshot(self) -> dict[str, Tool]:
        return dict(self._tools)

    def specs(self, capabilities: tuple[str, ...]) -> tuple[ToolSpec, ...]:
        missing = [name for name in capabilities if name not in self._tools]
        if missing:
            raise KeyError(f"unknown capabilities: {', '.join(missing)}")
        return tuple(self._tools[name].spec for name in capabilities)
