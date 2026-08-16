"""Model boundary. Vendor SDK response objects must not cross this boundary."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Message:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ToolCall:
    call_id: str
    capability: str
    arguments: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0


@dataclass(frozen=True, slots=True)
class ModelRequest:
    messages: tuple[Message, ...] = ()
    system_prompt: str = ""
    tools: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class ModelResponse:
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    usage: Usage = field(default_factory=Usage)
    finish_reason: str = "stop"


class ModelProvider(Protocol):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        ...
