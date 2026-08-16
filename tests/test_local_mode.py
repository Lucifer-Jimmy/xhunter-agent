import json
import sys
import unittest

from xhunter.adapters.memory import FakeSandbox
from xhunter.adapters.sandbox import LocalSandbox
from xhunter.application.bootstrap import (
    SandboxConfig,
    UnsafeLocalSandboxError,
    build_mission_sandbox,
)
from xhunter.contracts.sandbox import SandboxRequest, SandboxResult
from xhunter.contracts.tool import ToolRequest
from xhunter.plugins.builtin import PythonTool, ShellTool
from xhunter.runtime.capability import CapabilityRegistry


class LocalSandboxTests(unittest.IsolatedAsyncioTestCase):
    async def test_executes_argv_without_shell_parsing(self) -> None:
        sandbox = LocalSandbox({})
        result = await sandbox.execute(
            SandboxRequest(
                (
                    sys.executable,
                    "-I",
                    "-c",
                    "import sys; print(sys.argv[1])",
                    "value; echo should-not-run",
                )
            )
        )
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout.strip(), "value; echo should-not-run")

    async def test_does_not_inherit_host_credentials(self) -> None:
        sandbox = LocalSandbox(
            {
                "PATH": "/usr/bin:/bin",
                "OPENAI_API_KEY": "secret",
                "DATABASE_URL": "postgres://secret",
            }
        )
        code = (
            "import json, os; "
            "print(json.dumps({k: os.environ.get(k) for k in "
            "['OPENAI_API_KEY', 'DATABASE_URL']}))"
        )
        result = await sandbox.execute(
            SandboxRequest((sys.executable, "-I", "-c", code))
        )
        self.assertEqual(
            json.loads(result.stdout),
            {"OPENAI_API_KEY": None, "DATABASE_URL": None},
        )

    async def test_timeout_kills_process(self) -> None:
        sandbox = LocalSandbox({})
        result = await sandbox.execute(
            SandboxRequest(
                (sys.executable, "-I", "-c", "import time; time.sleep(5)"),
                timeout_seconds=0.01,
            )
        )
        self.assertEqual(result.exit_code, 124)
        self.assertTrue(result.timed_out)

    async def test_unknown_command_is_structured_failure(self) -> None:
        result = await LocalSandbox({}).execute(
            SandboxRequest(("xhunter-command-that-does-not-exist",))
        )
        self.assertEqual(result.exit_code, 127)
        self.assertTrue(result.stderr)


class LocalModeBootstrapTests(unittest.TestCase):
    def test_real_mission_fails_closed_without_explicit_override(self) -> None:
        with self.assertRaises(UnsafeLocalSandboxError):
            build_mission_sandbox(SandboxConfig("local"), {})

    def test_explicit_override_builds_local_sandbox(self) -> None:
        sandbox = build_mission_sandbox(
            SandboxConfig("local"),
            {"XHUNTER_ALLOW_UNSAFE_LOCAL_SANDBOX": "1"},
        )
        self.assertIsInstance(sandbox, LocalSandbox)


class BuiltinToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_shell_tool_delegates_to_sandbox(self) -> None:
        sandbox = FakeSandbox(SandboxResult(0, stdout="shell output"))
        result = await ShellTool(sandbox).execute(
            ToolRequest("system.shell", {"command": ["printf", "hello"]})
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.output, "shell output")
        self.assertEqual(sandbox.requests[0].command, ("printf", "hello"))

    async def test_python_tool_delegates_to_sandbox(self) -> None:
        sandbox = FakeSandbox(SandboxResult(0, stdout="42\n"))
        result = await PythonTool(sandbox, executable="python3").execute(
            ToolRequest("code.python", {"code": "print(6 * 7)"})
        )
        self.assertTrue(result.ok)
        self.assertEqual(sandbox.requests[0].command, (
            "python3",
            "-I",
            "-c",
            "print(6 * 7)",
        ))

    def test_capability_registration_is_reversible(self) -> None:
        registry = CapabilityRegistry()
        tool = ShellTool(FakeSandbox())
        dispose = registry.register(tool)
        self.assertIs(registry.resolve("system.shell"), tool)
        dispose()
        self.assertIsNone(registry.resolve("system.shell"))
