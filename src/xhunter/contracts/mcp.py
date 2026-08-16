"""MCP boundary DTOs. Concrete transports run outside the Host execution plane."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class McpServerSpec:
    server_id: str
    command: tuple[str, ...]
    environment: dict[str, str] = field(default_factory=dict)
    working_directory: str | None = None


@dataclass(frozen=True, slots=True)
class McpToolSpec:
    server_id: str
    name: str
    description: str = ""
    input_schema: dict[str, object] = field(default_factory=dict)

    @property
    def capability(self) -> str:
        return f"mcp.{self.server_id}.{self.name}"


@dataclass(frozen=True, slots=True)
class McpCallResult:
    content: str
    is_error: bool = False


class McpTransport(Protocol):
    async def list_tools(self, server: McpServerSpec) -> tuple[McpToolSpec, ...]:
        ...

    async def call_tool(
        self,
        server: McpServerSpec,
        tool_name: str,
        arguments: dict[str, object],
    ) -> McpCallResult:
        ...

    async def close(self) -> None:
        ...
