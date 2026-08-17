import unittest

from xhunter.adapters.memory import (
    EchoTool,
    FakeModelProvider,
    FakeSandbox,
    InProcessEventBus,
)
from xhunter.application.tool_runtime import build_tool_dispatcher
from xhunter.contracts.agent_executor import AgentExecutionResult
from xhunter.contracts.model import ModelResponse, ToolCall
from xhunter.contracts.sandbox import SandboxResult
from xhunter.contracts.tool import ToolRequest
from xhunter.contracts.verification import VerificationContext
from xhunter.domains.ctf import CtfChallenge, CtfDomain, CtfFlagVerifier
from xhunter.orchestration.policies import (
    BudgetController,
    BudgetLimits,
    ScopePolicy,
    ScopePolicyConfig,
)
from xhunter.runtime.agent import ReActAgentExecutor
from xhunter.runtime.capability import CapabilityRegistry
from xhunter.runtime.skill import SkillCatalog
from xhunter.services import ContextService


class CtfDomainTests(unittest.IsolatedAsyncioTestCase):
    def test_web_challenge_creates_scoped_mission_task_and_profile(self) -> None:
        state = CtfDomain().create_initial_state(
            CtfChallenge(
                "Login Lab",
                "web",
                ("challenge.local",),
                "登录页面存在未知漏洞，请找到 flag。",
            )
        )
        self.assertEqual(state.mission.scope, ("challenge.local",))
        self.assertEqual(state.task.mission_id, state.mission.id)
        self.assertIn("network.http", state.task.required_capabilities)
        self.assertEqual(
            state.task.required_capabilities,
            state.profile.required_capabilities,
        )
        self.assertIn("登录页面存在未知漏洞", state.task.objective)

    async def test_flag_verifier_accepts_matching_candidate(self) -> None:
        verifier = CtfFlagVerifier(r"flag\{[a-z0-9_-]+\}")
        accepted = await verifier.verify(
            AgentExecutionResult("result: flag{solved_1}", 1),
            VerificationContext("m1", "t1"),
        )
        rejected = await verifier.verify(
            AgentExecutionResult("no candidate", 1),
            VerificationContext("m1", "t1"),
        )
        self.assertTrue(accepted.accepted)
        self.assertFalse(rejected.accepted)

    async def test_browser_target_outside_scope_is_denied_before_tool(self) -> None:
        policy = ScopePolicy(ScopePolicyConfig(("challenge.local",)))
        decision = await policy.authorize(
            ToolRequest("browser.web", {"url": "https://platform.local"})
        )
        self.assertFalse(decision.allowed)

    async def test_ctf_profile_runs_through_shared_agent_runtime(self) -> None:
        state = CtfDomain().create_initial_state(
            CtfChallenge(
                "Echo Lab",
                "misc",
                ("challenge.local",),
                "分析 Echo 服务并取得 flag。",
            )
        )
        registry = CapabilityRegistry()
        registry.register(
            EchoTool(FakeSandbox(SandboxResult(0, stdout="flag{local_test}")))
        )
        profile = state.profile.__class__(
            state.profile.role,
            required_capabilities=("test.echo",),
            max_steps=3,
        )
        request = ContextService(SkillCatalog(), registry).build_agent_request(
            str(state.mission.id), str(state.task.id), profile
        )
        agent = ReActAgentExecutor(
            FakeModelProvider(
                [
                    ModelResponse(
                        tool_calls=(ToolCall("call-1", "test.echo", {}),)
                    ),
                    ModelResponse(content="flag{local_test}"),
                ]
            ),
            build_tool_dispatcher(
                registry,
                BudgetController(BudgetLimits(10, 10, 60)),
                ScopePolicy(ScopePolicyConfig(state.mission.scope)),
                InProcessEventBus(),
            ),
        )
        result = await agent.execute(request)
        verification = await CtfFlagVerifier(r"flag\{[^}\r\n]+\}").verify(
            result, VerificationContext(str(state.mission.id), str(state.task.id))
        )
        self.assertTrue(verification.accepted)
