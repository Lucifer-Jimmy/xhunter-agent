"""Small, framework-free ReAct loop for the first vertical slice."""

from xhunter.contracts.agent_executor import AgentExecutionRequest, AgentExecutionResult
from xhunter.contracts.model import Message, ModelProvider, ModelRequest
from xhunter.contracts.tool import ToolRequest
from xhunter.orchestration.dispatcher import ToolDispatcher


class ReActAgentExecutor:
    def __init__(self, model: ModelProvider, dispatcher: ToolDispatcher) -> None:
        self._model = model
        self._dispatcher = dispatcher

    async def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        messages = list(request.messages)
        tool_results = []

        for step in range(1, request.max_steps + 1):
            response = await self._model.generate(
                ModelRequest(
                    system_prompt=request.system_prompt,
                    messages=tuple(messages),
                    tools=request.tools,
                )
            )
            if not response.tool_calls:
                return AgentExecutionResult(
                    response.content or "", step, tuple(tool_results)
                )

            for call in response.tool_calls:
                result = await self._dispatcher.dispatch(
                    ToolRequest(
                        capability=call.capability,
                        arguments=call.arguments,
                        mission_id=request.mission_id,
                        task_id=request.task_id,
                    )
                )
                tool_results.append(result)
                observation = result.output if result.ok else f"ERROR: {result.error}"
                messages.append(Message("tool", observation))

        return AgentExecutionResult(
            "agent step budget exhausted", request.max_steps, tuple(tool_results)
        )
