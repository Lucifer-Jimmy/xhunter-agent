"""Context construction contract."""

from typing import Protocol

from xhunter.contracts.agent_executor import AgentExecutionRequest
from xhunter.contracts.model import Message
from xhunter.kernel.entities import Mission, Task


class ContextProvider(Protocol):
    def build(
        self,
        mission: Mission,
        task: Task,
        messages: tuple[Message, ...] = (),
    ) -> AgentExecutionRequest:
        ...
