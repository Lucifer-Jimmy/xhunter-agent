import unittest

from xhunter.adapters.memory import InProcessEventBus
from xhunter.application.tool_runtime import build_tool_dispatcher
from xhunter.contracts.event_bus import Event
from xhunter.contracts.tool import ToolRequest
from xhunter.orchestration.policies import (
    BudgetController,
    BudgetLimits,
    ScopePolicy,
    ScopePolicyConfig,
)
from xhunter.runtime.capability import CapabilityRegistry


class ToolUnavailableTests(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_capability_is_audited_before_rejection_returns(self) -> None:
        events: list[Event] = []
        bus = InProcessEventBus()

        async def capture(event: Event) -> None:
            events.append(event)

        bus.subscribe("tool.unavailable", capture)
        dispatcher = build_tool_dispatcher(
            CapabilityRegistry(),
            BudgetController(BudgetLimits(1, 1, 60)),
            ScopePolicy(ScopePolicyConfig(())),
            bus,
        )
        result = await dispatcher.dispatch(
            ToolRequest("missing.tool", mission_id="m1", task_id="t1")
        )
        self.assertTrue(result.rejected)
        self.assertEqual([event.name for event in events], ["tool.unavailable"])
