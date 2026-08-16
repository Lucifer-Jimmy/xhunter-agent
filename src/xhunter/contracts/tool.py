"""Tool boundary and dispatcher middleware signature."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol


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

    async def execute(self, request: ToolRequest) -> ToolResult:
        ...
