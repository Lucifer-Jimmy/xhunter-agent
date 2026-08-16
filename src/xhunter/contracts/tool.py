"""Tool boundary and dispatcher middleware signature."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol

TOOL_API_V1 = "1.0"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    capability: str
    description: str
    input_schema: dict[str, object]
    api_version: str = TOOL_API_V1

    def validate(self) -> None:
        if not self.capability or not self.description:
            raise ValueError("tool capability and description must not be empty")
        if self.api_version.split(".", maxsplit=1)[0] != TOOL_API_V1.split(".")[0]:
            raise ValueError(f"incompatible Tool API version: {self.api_version}")
        if self.input_schema.get("type") != "object":
            raise ValueError("tool input schema root type must be object")


@dataclass(frozen=True, slots=True)
class ToolRequest:
    capability: str
    arguments: dict[str, object] = field(default_factory=dict)
    mission_id: str = ""
    task_id: str = ""


@dataclass(frozen=True, slots=True)
class ToolResult:
    ok: bool
    output: str = ""
    error: str | None = None
    rejected: bool = False

    @classmethod
    def rejected_result(cls, reason: str) -> "ToolResult":
        return cls(ok=False, error=reason, rejected=True)


ToolNext = Callable[[ToolRequest], Awaitable[ToolResult]]
ToolMiddleware = Callable[[ToolRequest, ToolNext], Awaitable[ToolResult]]


class Tool(Protocol):
    capability: str
    spec: ToolSpec

    async def execute(self, request: ToolRequest) -> ToolResult:
        ...
