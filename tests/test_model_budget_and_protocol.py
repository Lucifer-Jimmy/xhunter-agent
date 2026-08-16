import unittest
from collections.abc import Mapping

from xhunter.adapters.memory import FakeModelProvider, InProcessEventBus
from xhunter.adapters.models import (
    OpenAICompatibleConfig,
    OpenAICompatibleModelProvider,
)
from xhunter.contracts.agent_executor import AgentExecutionRequest
from xhunter.contracts.event_bus import Event
from xhunter.contracts.model import (
    Message,
    ModelRequest,
    ModelResponse,
    ToolCall,
    Usage,
)
from xhunter.orchestration.dispatcher import ToolDispatcher
from xhunter.runtime.agent import (
    BudgetedModelProvider,
    ModelBudgetExceeded,
    ModelBudgetLimits,
    ReActAgentExecutor,
)


class RecordingTransport:
    def __init__(self) -> None:
        self.payloads: list[dict[str, object]] = []

    async def post(
        self,
        url: str,
        headers: Mapping[str, str],
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        del url, headers, timeout_seconds
        self.payloads.append(payload)
        return {
            "choices": [{"message": {"content": "done"}, "finish_reason": "stop"}]
        }


class ToolMessageProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_adapter_serializes_assistant_calls_and_tool_call_ids(self) -> None:
        transport = RecordingTransport()
        provider = OpenAICompatibleModelProvider(
            OpenAICompatibleConfig("https://model.example/v1", "secret", "model"),
            transport,
        )
        call = ToolCall("call-1", "code.python", {"code": "print(1)"})
        await provider.generate(
            ModelRequest(
                mission_id="m1",
                task_id="t1",
                messages=(
                    Message("assistant", None, tool_calls=(call,)),
                    Message("tool", "1", tool_call_id="call-1"),
                ),
            )
        )
        messages = transport.payloads[0]["messages"]
        assert isinstance(messages, list)
        assistant = messages[0]
        tool = messages[1]
        assert isinstance(assistant, dict) and isinstance(tool, dict)
        self.assertEqual(assistant["tool_calls"][0]["id"], "call-1")
        self.assertEqual(tool["tool_call_id"], "call-1")

    async def test_react_preserves_assistant_tool_call_in_second_request(self) -> None:
        model = FakeModelProvider(
            [
                ModelResponse(
                    tool_calls=(ToolCall("call-1", "missing.tool", {}),)
                ),
                ModelResponse(content="done"),
            ]
        )
        await ReActAgentExecutor(model, ToolDispatcher({})).execute(
            AgentExecutionRequest(mission_id="m1", task_id="t1")
        )
        history = model.requests[1].messages
        self.assertEqual(history[0].role, "assistant")
        self.assertEqual(history[0].tool_calls[0].call_id, "call-1")
        self.assertEqual(history[1].tool_call_id, "call-1")


class ModelBudgetTests(unittest.IsolatedAsyncioTestCase):
    async def test_blocks_next_call_after_task_token_limit_is_reached(self) -> None:
        provider = FakeModelProvider(
            [
                ModelResponse(content="one", usage=Usage(6, 4, 0.5)),
                ModelResponse(content="must not run"),
            ]
        )
        budgeted = BudgetedModelProvider(
            provider,
            ModelBudgetLimits(100, 10, 100, 10),
            InProcessEventBus(),
        )
        request = ModelRequest(mission_id="m1", task_id="t1")
        await budgeted.generate(request)
        with self.assertRaises(ModelBudgetExceeded):
            await budgeted.generate(request)
        self.assertEqual(len(provider.requests), 1)

    async def test_publishes_usage_only_without_prompt_content(self) -> None:
        events: list[Event] = []
        bus = InProcessEventBus()

        async def capture(event: Event) -> None:
            events.append(event)

        bus.subscribe("model.called", capture)
        bus.subscribe("model.completed", capture)
        budgeted = BudgetedModelProvider(
            FakeModelProvider(
                [ModelResponse(content="answer", usage=Usage(3, 2, 0.01))]
            ),
            ModelBudgetLimits(100, 100, 10, 10),
            bus,
        )
        await budgeted.generate(
            ModelRequest(
                mission_id="m1",
                task_id="t1",
                messages=(Message("user", "sensitive prompt"),),
            )
        )
        serialized = repr([event.payload for event in events])
        self.assertNotIn("sensitive prompt", serialized)
        self.assertEqual([event.name for event in events], [
            "model.called",
            "model.completed",
        ])

    async def test_missing_scope_ids_fails_closed(self) -> None:
        budgeted = BudgetedModelProvider(
            FakeModelProvider([]),
            ModelBudgetLimits(100, 100, 10, 10),
            InProcessEventBus(),
        )
        with self.assertRaises(ModelBudgetExceeded):
            await budgeted.generate(ModelRequest())
