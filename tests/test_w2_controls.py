import asyncio
import unittest

from xhunter.adapters.memory import (
    EchoTool,
    FakeModelProvider,
    FakeSandbox,
    InProcessEventBus,
)
from xhunter.application.tool_runtime import build_tool_dispatcher
from xhunter.contracts.agent_executor import AgentExecutionRequest
from xhunter.contracts.event_bus import Event
from xhunter.contracts.model import ModelResponse, ToolCall
from xhunter.contracts.sandbox import SandboxResult
from xhunter.contracts.tool import ToolRequest
from xhunter.orchestration.dispatcher import ToolDispatcher
from xhunter.orchestration.policies import (
    BudgetController,
    BudgetLimits,
    ScopePolicy,
    ScopePolicyConfig,
)
from xhunter.plugins.builtin import HttpTool
from xhunter.runtime.agent import ReActAgentExecutor
from xhunter.runtime.capability import CapabilityRegistry


class CapabilityResolutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_dispatcher_observes_registration_and_disposal(self) -> None:
        registry = CapabilityRegistry()
        dispatcher = ToolDispatcher(registry.resolve)
        request = ToolRequest("test.echo", {"value": "hello"})
        self.assertTrue((await dispatcher.dispatch(request)).rejected)

        dispose = registry.register(
            EchoTool(FakeSandbox(SandboxResult(0, stdout="hello")))
        )
        self.assertEqual((await dispatcher.dispatch(request)).output, "hello")
        dispose()
        self.assertTrue((await dispatcher.dispatch(request)).rejected)


class BudgetControllerTests(unittest.IsolatedAsyncioTestCase):
    async def test_task_budget_rejects_before_tool_execution(self) -> None:
        budget = BudgetController(BudgetLimits(10, 1, 60))
        calls = 0

        async def execute(_request):
            nonlocal calls
            calls += 1
            from xhunter.contracts.tool import ToolResult

            return ToolResult(ok=True)

        request = ToolRequest("test.echo", mission_id="m1", task_id="t1")
        self.assertTrue((await budget.middleware(request, execute)).ok)
        result = await budget.middleware(request, execute)
        self.assertTrue(result.rejected)
        self.assertEqual(calls, 1)

    async def test_concurrent_calls_cannot_oversell_mission_budget(self) -> None:
        budget = BudgetController(BudgetLimits(3, 3, 60))

        async def execute(_request):
            await asyncio.sleep(0)
            from xhunter.contracts.tool import ToolResult

            return ToolResult(ok=True)

        results = await asyncio.gather(
            *(
                budget.middleware(
                    ToolRequest("test.echo", mission_id="m1", task_id=f"t{index}"),
                    execute,
                )
                for index in range(10)
            )
        )
        self.assertEqual(sum(result.ok for result in results), 3)
        self.assertEqual(sum(result.rejected for result in results), 7)

    async def test_wall_clock_budget_is_fail_closed(self) -> None:
        now = 10.0
        budget = BudgetController(BudgetLimits(10, 10, 5), lambda: now)

        async def execute(_request):
            from xhunter.contracts.tool import ToolResult

            return ToolResult(ok=True)

        request = ToolRequest("test.echo", mission_id="m1", task_id="t1")
        self.assertTrue((await budget.middleware(request, execute)).ok)
        now = 15.0
        self.assertTrue((await budget.middleware(request, execute)).rejected)


class ScopePolicyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.policy = ScopePolicy(
            ScopePolicyConfig(
                allowed_targets=("challenge.local", "10.10.0.0/16"),
                blocked_targets=("10.10.0.1", "platform.local"),
            )
        )

    async def test_allows_explicit_in_scope_url(self) -> None:
        decision = await self.policy.authorize(
            ToolRequest("network.http", {"url": "http://challenge.local:8080/a"})
        )
        self.assertTrue(decision.allowed)

    async def test_allows_in_scope_cidr_address(self) -> None:
        decision = await self.policy.authorize(
            ToolRequest("network.http", {"target": "10.10.4.2:9000"})
        )
        self.assertTrue(decision.allowed)

    async def test_blocked_target_wins_over_allowed_network(self) -> None:
        decision = await self.policy.authorize(
            ToolRequest("network.http", {"host": "10.10.0.1"})
        )
        self.assertFalse(decision.allowed)
        self.assertIn("blocked", decision.reason)

    async def test_network_action_without_target_is_denied(self) -> None:
        decision = await self.policy.authorize(ToolRequest("network.http", {}))
        self.assertFalse(decision.allowed)

    async def test_non_network_capability_is_not_target_scoped(self) -> None:
        decision = await self.policy.authorize(ToolRequest("code.python", {}))
        self.assertTrue(decision.allowed)


class DefaultMiddlewareChainTests(unittest.IsolatedAsyncioTestCase):
    async def test_policy_denial_short_circuits_tool_and_is_audited(self) -> None:
        registry = CapabilityRegistry()
        sandbox = FakeSandbox(SandboxResult(0, stdout="unexpected"))
        registry.register(HttpTool(sandbox))
        events: list[Event] = []
        bus = InProcessEventBus()

        async def capture(event: Event) -> None:
            events.append(event)

        bus.subscribe("tool.called", capture)
        bus.subscribe("tool.completed", capture)
        bus.subscribe("tool.rejected", capture)
        dispatcher = build_tool_dispatcher(
            registry,
            BudgetController(BudgetLimits(10, 10, 60)),
            ScopePolicy(ScopePolicyConfig(allowed_targets=())),
            bus,
        )
        result = await dispatcher.dispatch(
            ToolRequest(
                "network.http",
                {"url": "http://outside.local"},
                mission_id="m1",
                task_id="t1",
            )
        )
        self.assertTrue(result.rejected)
        self.assertEqual(sandbox.requests, [])
        self.assertEqual(
            [event.name for event in events], ["tool.called", "tool.rejected"]
        )

    async def test_agent_propagates_mission_and_task_to_audit_events(self) -> None:
        registry = CapabilityRegistry()
        registry.register(EchoTool(FakeSandbox(SandboxResult(0, stdout="observed"))))
        events: list[Event] = []
        bus = InProcessEventBus()

        async def capture(event: Event) -> None:
            events.append(event)

        bus.subscribe("tool.called", capture)
        bus.subscribe("tool.completed", capture)
        dispatcher = build_tool_dispatcher(
            registry,
            BudgetController(BudgetLimits(10, 10, 60)),
            ScopePolicy(ScopePolicyConfig(allowed_targets=())),
            bus,
        )
        agent = ReActAgentExecutor(
            FakeModelProvider(
                [
                    ModelResponse(
                        tool_calls=(ToolCall("1", "test.echo", {"value": "x"}),)
                    ),
                    ModelResponse(content="done"),
                ]
            ),
            dispatcher,
        )
        result = await agent.execute(
            AgentExecutionRequest(mission_id="m1", task_id="t1")
        )
        self.assertEqual(result.content, "done")
        self.assertEqual([event.name for event in events], [
            "tool.called",
            "tool.completed",
        ])
        payloads = [event.payload for event in events]
        self.assertTrue(all(isinstance(payload, dict) for payload in payloads))
        self.assertTrue(
            all(
                payload["mission_id"] == "m1"
                for payload in payloads
                if isinstance(payload, dict)
            )
        )
