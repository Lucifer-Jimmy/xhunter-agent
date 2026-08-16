"""Domain-independent result verification boundary."""

from dataclasses import dataclass
from typing import Protocol

from xhunter.contracts.agent_executor import AgentExecutionResult


@dataclass(frozen=True, slots=True)
class VerificationContext:
    mission_id: str
    task_id: str


@dataclass(frozen=True, slots=True)
class VerificationResult:
    accepted: bool
    reason: str = ""


class Verifier(Protocol):
    async def verify(
        self, result: AgentExecutionResult, context: VerificationContext
    ) -> VerificationResult:
        ...
