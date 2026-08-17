import unittest

from xhunter.adapters.memory import FakeModelProvider, FakeSandbox
from xhunter.contracts.model import ModelResponse
from xhunter.contracts.sandbox import SandboxResult
from xhunter.contracts.tool import ToolRequest, ToolResult, ToolSpec
from xhunter.orchestration.dispatcher import ToolDispatcher
from xhunter.plugins.builtin import FilesystemTool, HttpTool, PythonTool, ShellTool
from xhunter.runtime.agent import ReActAgentExecutor
from xhunter.runtime.capability import CapabilityRegistry
from xhunter.runtime.skill import Skill, SkillCatalog
from xhunter.services import AgentProfile, ContextService


class ToolSpecTests(unittest.TestCase):
    def test_registry_exposes_only_requested_capability_specs(self) -> None:
        registry = CapabilityRegistry()
        registry.register(ShellTool(FakeSandbox()))
        registry.register(PythonTool(FakeSandbox()))
        specs = registry.specs(("code.python",))
        self.assertEqual([spec.capability for spec in specs], ["code.python"])

    def test_registry_rejects_invalid_tool_schema(self) -> None:
        class InvalidTool:
            capability = "test.invalid"
            spec = ToolSpec(capability, "Invalid schema", {"type": "string"})

            async def execute(self, request: ToolRequest) -> ToolResult:
                del request
                raise AssertionError("must not execute")

        with self.assertRaises(ValueError):
            CapabilityRegistry().register(InvalidTool())


class ContextServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_skills_and_allowed_tools_reach_model_request(self) -> None:
        skills = SkillCatalog()
        skills.register(
            Skill(
                "ctf.web.sqli",
                "SQL Injection",
                "1.0.0",
                "Probe parameter boundaries and preserve evidence.",
            )
        )
        capabilities = CapabilityRegistry()
        capabilities.register(HttpTool(FakeSandbox()))
        capabilities.register(ShellTool(FakeSandbox()))
        context = ContextService(skills, capabilities).build_agent_request(
            "mission-1",
            "task-1",
            AgentProfile(
                role="You are a CTF web analyst.",
                skill_ids=("ctf.web.sqli",),
                required_capabilities=("network.http",),
            ),
        )
        model = FakeModelProvider([ModelResponse(content="done")])
        result = await ReActAgentExecutor(
            model, ToolDispatcher(capabilities.resolve)
        ).execute(context)

        self.assertEqual(result.content, "done")
        self.assertIn("CTF web analyst", model.requests[0].system_prompt)
        self.assertIn("Probe parameter boundaries", model.requests[0].system_prompt)
        self.assertEqual(
            [spec.capability for spec in model.requests[0].tools],
            ["network.http"],
        )

    def test_unknown_profile_capability_fails_closed(self) -> None:
        with self.assertRaises(KeyError):
            ContextService(SkillCatalog(), CapabilityRegistry()).build_agent_request(
                "mission-1",
                "task-1",
                AgentProfile("analyst", required_capabilities=("network.http",)),
            )

    def test_profile_context_injects_objective_and_scope(self) -> None:
        from xhunter.kernel.entities import Mission, Task
        from xhunter.kernel.types import MissionId, TaskId
        from xhunter.services import ProfileContextProvider

        provider = ProfileContextProvider(
            ContextService(SkillCatalog(), CapabilityRegistry()),
            lambda _task: AgentProfile("analyst"),
        )
        request = provider.build(
            Mission(MissionId("m1"), "challenge", ("web.challenge.ctf.show",)),
            Task(TaskId("t1"), MissionId("m1"), "Find the flag"),
        )
        self.assertIn("Find the flag", request.messages[0].content or "")
        self.assertIn(
            "web.challenge.ctf.show", request.messages[0].content or ""
        )
        self.assertIn("Do not inspect the Host", request.messages[0].content or "")


class SandboxBackedToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_tool_builds_curl_request_and_sends_body_on_stdin(self) -> None:
        sandbox = FakeSandbox(SandboxResult(0, stdout="HTTP/1.1 200 OK\n\nhello"))
        result = await HttpTool(sandbox).execute(
            ToolRequest(
                "network.http",
                {
                    "url": "http://challenge.local/api",
                    "method": "post",
                    "headers": {"Content-Type": "application/json"},
                    "body": '{"probe": true}',
                },
            )
        )
        sandbox_request = sandbox.requests[0]
        self.assertTrue(result.ok)
        self.assertEqual(sandbox_request.command[0], "curl")
        self.assertIn("http://challenge.local/api", sandbox_request.command)
        self.assertNotIn('{"probe": true}', sandbox_request.command)
        self.assertEqual(sandbox_request.stdin, b'{"probe": true}')

    async def test_filesystem_tool_delegates_payload_to_sandbox(self) -> None:
        sandbox = FakeSandbox(SandboxResult(0, stdout='{"written": 5}\n'))
        result = await FilesystemTool(sandbox).execute(
            ToolRequest(
                "filesystem.workspace",
                {"operation": "write", "path": "notes.txt", "content": "hello"},
            )
        )
        sandbox_request = sandbox.requests[0]
        self.assertTrue(result.ok)
        self.assertEqual(sandbox_request.command[:3], ("python3", "-I", "-c"))
        self.assertIn(b'"path": "notes.txt"', sandbox_request.stdin or b"")
