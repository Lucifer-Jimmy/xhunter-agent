import unittest

from xhunter.adapters.memory import (
    EchoTool,
    FakeSandbox,
    InProcessEventBus,
)
from xhunter.application.tool_runtime import build_tool_dispatcher
from xhunter.contracts.event_bus import Event
from xhunter.contracts.tool import ToolRequest, ToolResult, ToolSpec
from xhunter.orchestration.policies import (
    BudgetController,
    BudgetLimits,
    ScopePolicy,
    ScopePolicyConfig,
)
from xhunter.runtime.capability import CapabilityRegistry


class FailingTool:
    capability = "test.failure"
    spec = ToolSpec(capability, "Fail for audit test", {"type": "object"})

    async def execute(self, request: ToolRequest) -> ToolResult:
        del request
        raise RuntimeError("secret exception detail")


class ToolAuditTests(unittest.IsolatedAsyncioTestCase):
    async def test_budget_rejection_has_attempt_and_terminal_event(self) -> None:
        events, dispatcher = self._dispatcher(BudgetLimits(0, 0, 60))
        result = await dispatcher.dispatch(
            ToolRequest("test.echo", mission_id="m1", task_id="t1")
        )
        self.assertTrue(result.rejected)
        self.assertEqual(
            [event.name for event in events], ["tool.called", "tool.rejected"]
        )

    async def test_tool_exception_emits_type_without_exception_text(self) -> None:
        registry = CapabilityRegistry()
        registry.register(FailingTool())
        events: list[Event] = []
        bus = InProcessEventBus()

        async def capture(event: Event) -> None:
            events.append(event)

        bus.subscribe("tool.called", capture)
        bus.subscribe("tool.failed", capture)
        dispatcher = build_tool_dispatcher(
            registry,
            BudgetController(BudgetLimits(10, 10, 60)),
            ScopePolicy(ScopePolicyConfig(())),
            bus,
        )
        with self.assertRaises(RuntimeError):
            await dispatcher.dispatch(
                ToolRequest("test.failure", mission_id="m1", task_id="t1")
            )
        payload = events[-1].payload
        assert isinstance(payload, dict)
        self.assertEqual(payload["error_type"], "RuntimeError")
        self.assertNotIn("secret exception detail", repr(payload))

    def _dispatcher(self, limits: BudgetLimits):
        registry = CapabilityRegistry()
        registry.register(EchoTool(FakeSandbox()))
        events: list[Event] = []
        bus = InProcessEventBus()

        async def capture(event: Event) -> None:
            events.append(event)

        bus.subscribe("tool.called", capture)
        bus.subscribe("tool.rejected", capture)
        dispatcher = build_tool_dispatcher(
            registry,
            BudgetController(limits),
            ScopePolicy(ScopePolicyConfig(())),
            bus,
        )
        return events, dispatcher
