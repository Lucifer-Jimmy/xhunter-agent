"""Replaceable agent execution boundary."""

from dataclasses import dataclass, field
from typing import Protocol

from xhunter.contracts.model import Message
from xhunter.contracts.tool import ToolResult


@dataclass(frozen=True, slots=True)
class AgentExecutionRequest:
    mission_id: str = ""
    task_id: str = ""
    system_prompt: str = ""
    messages: tuple[Message, ...] = ()
    max_steps: int = 8


@dataclass(frozen=True, slots=True)
class AgentExecutionResult:
    content: str
    steps: int
    tool_results: tuple[ToolResult, ...] = field(default_factory=tuple)


class AgentExecutor(Protocol):
    async def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        ...
