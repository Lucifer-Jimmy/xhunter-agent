import asyncio
import unittest

from xhunter.adapters.memory import (
    EchoTool,
    FakeModelProvider,
    FakeSandbox,
    InProcessEventBus,
    MemoryCheckpointStore,
    MemoryTaskRepository,
)
from xhunter.contracts.agent_executor import AgentExecutionRequest
from xhunter.contracts.event_bus import Event
from xhunter.contracts.model import ModelRequest, ModelResponse, ToolCall
from xhunter.contracts.sandbox import SandboxRequest, SandboxResult
from xhunter.contracts.tool import ToolRequest, ToolResult
from xhunter.kernel.entities import Task, TaskStatus
from xhunter.kernel.types import MissionId, TaskId
from xhunter.orchestration.dispatcher import ToolDispatcher
from xhunter.runtime.agent import AgentExecutionTimeout, ReActAgentExecutor


class W1Tests(unittest.IsolatedAsyncioTestCase):
    async def test_pending_tasks_are_scoped_to_mission(self) -> None:
        repository = MemoryTaskRepository()
        await repository.save(Task(TaskId("one"), MissionId("m1"), "first"))
        await repository.save(Task(TaskId("two"), MissionId("m2"), "second"))
        await repository.save(
            Task(TaskId("done"), MissionId("m1"), "done", status=TaskStatus.COMPLETED)
        )
        pending = await repository.list_pending(MissionId("m1"))
        self.assertEqual([task.id for task in pending], [TaskId("one")])

    async def test_checkpoint_store_copies_state(self) -> None:
        store = MemoryCheckpointStore()
        state = {"step": 1, "tool": "test.echo"}
        await store.save("task-1", state)
        state["step"] = 2
        self.assertEqual(await store.load("task-1"), {"step": 1, "tool": "test.echo"})
        await store.delete("task-1")
        self.assertIsNone(await store.load("task-1"))

    async def test_event_handler_failure_does_not_break_publish(self) -> None:
        bus = InProcessEventBus()
        received: list[str] = []

        async def failing(_event: Event) -> None:
            raise RuntimeError("observer failure")

        async def healthy(event: Event) -> None:
            received.append(event.name)

        dispose = bus.subscribe("tool.completed", failing)
        bus.subscribe("tool.completed", healthy)
        await bus.publish(Event("tool.completed", {}))
        self.assertEqual(received, ["tool.completed"])
        dispose()

    async def test_fake_sandbox_records_execution_boundary(self) -> None:
        sandbox = FakeSandbox()
        request = SandboxRequest(("printf", "hello"))
        result = await sandbox.execute(request)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(sandbox.requests, [request])

    async def test_react_loop_dispatches_tool_then_returns_answer(self) -> None:
        model = FakeModelProvider(
            [
                ModelResponse(
                    tool_calls=(ToolCall("1", "test.echo", {"value": "hello"}),)
                ),
                ModelResponse(content="done"),
            ]
        )
        sandbox = FakeSandbox(SandboxResult(exit_code=0, stdout="hello"))
        agent = ReActAgentExecutor(
            model,
            ToolDispatcher({"test.echo": EchoTool(sandbox)}),
        )
        result = await agent.execute(AgentExecutionRequest())
        self.assertEqual(result.content, "done")
        self.assertEqual(result.steps, 2)
        self.assertEqual(result.tool_results[0].output, "hello")

    async def test_dispatcher_short_circuits_when_policy_denies(self) -> None:
        called = False

        async def policy(request, _next):
            return ToolResult.rejected_result(f"denied: {request.capability}")

        class RecordingTool(EchoTool):
            async def execute(self, request):
                nonlocal called
                called = True
                return await super().execute(request)

        result = await ToolDispatcher(
            {"test.echo": RecordingTool(FakeSandbox())}, [policy]
        ).dispatch(ToolRequest("test.echo", {"value": "blocked"}))
        self.assertTrue(result.rejected)
        self.assertFalse(called)

    async def test_agent_wall_clock_timeout_cancels_slow_model(self) -> None:
        cancelled = False

        class SlowModel:
            async def generate(self, request: ModelRequest) -> ModelResponse:
                del request
                nonlocal cancelled
                try:
                    await asyncio.sleep(1)
                except asyncio.CancelledError:
                    cancelled = True
                    raise
                return ModelResponse(content="unexpected")

        agent = ReActAgentExecutor(SlowModel(), ToolDispatcher({}))
        with self.assertRaises(AgentExecutionTimeout):
            await agent.execute(AgentExecutionRequest(timeout_seconds=0.01))
        self.assertTrue(cancelled)
