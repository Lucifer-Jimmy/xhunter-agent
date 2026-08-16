"""Conservative generic verifier for the initial Mission loop."""

from xhunter.contracts.agent_executor import AgentExecutionResult
from xhunter.contracts.verification import (
    VerificationContext,
    VerificationResult,
)


class BasicVerifier:
    async def verify(
        self, result: AgentExecutionResult, context: VerificationContext
    ) -> VerificationResult:
        del context
        if result.content.strip() and not any(
            tool_result.rejected for tool_result in result.tool_results
        ):
            return VerificationResult(True, "agent returned a non-empty result")
        return VerificationResult(
            False, "agent result was empty or contained rejection"
        )
