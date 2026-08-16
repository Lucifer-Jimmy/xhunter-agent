import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path

from xhunter.adapters.memory import FakeSandbox
from xhunter.contracts.mcp import (
    McpCallResult,
    McpServerSpec,
    McpToolSpec,
)
from xhunter.contracts.plugin import PluginContext, PluginManifest
from xhunter.contracts.tool import ToolRequest
from xhunter.plugins.builtin import CoreToolsPlugin
from xhunter.runtime.capability import CapabilityRegistry
from xhunter.runtime.mcp import McpTool
from xhunter.runtime.plugin import PluginManager
from xhunter.runtime.skill import SkillCatalog, load_skill_directory


class SkillExtensionTests(unittest.TestCase):
    def test_load_register_render_and_dispose_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            (directory / "skill.toml").write_text(
                'id = "ctf.web.sqli"\n'
                'name = "SQL Injection"\n'
                'version = "1.0.0"\n'
                'tags = ["ctf", "web"]\n',
                encoding="utf-8",
            )
            (directory / "SKILL.md").write_text(
                "Test SQL input boundaries.", encoding="utf-8"
            )
            skill = load_skill_directory(directory)

        catalog = SkillCatalog()
        dispose = catalog.register(skill)
        self.assertEqual(catalog.render((skill.skill_id,)), skill.prompt)
        dispose()
        self.assertIsNone(catalog.get(skill.skill_id))


class PluginExtensionTests(unittest.TestCase):
    def test_core_tools_plugin_registers_and_disposes_tools(self) -> None:
        registry = CapabilityRegistry()
        manager = PluginManager(PluginContext(registry.register))
        self.assertIsNone(manager.start(CoreToolsPlugin(FakeSandbox())))
        self.assertIsNotNone(registry.resolve("system.shell"))
        self.assertIsNotNone(registry.resolve("code.python"))
        self.assertIsNotNone(registry.resolve("network.http"))
        self.assertIsNotNone(registry.resolve("filesystem.workspace"))
        manager.stop_all()
        self.assertIsNone(registry.resolve("system.shell"))
        self.assertIsNone(registry.resolve("code.python"))
        self.assertIsNone(registry.resolve("network.http"))
        self.assertIsNone(registry.resolve("filesystem.workspace"))

    def test_optional_plugin_failure_does_not_break_startup(self) -> None:
        class FailingPlugin:
            manifest = PluginManifest("test.failure", "Failure", "1.0.0")

            def start(self, context: PluginContext) -> Callable[[], None]:
                del context
                raise RuntimeError("startup failed")

        failure = PluginManager(
            PluginContext(CapabilityRegistry().register)
        ).start(FailingPlugin())
        self.assertIsNotNone(failure)
        assert failure is not None
        self.assertEqual(failure.plugin_id, "test.failure")

    def test_plugin_teardown_runs_in_reverse_order(self) -> None:
        stopped: list[str] = []

        class OrderedPlugin:
            def __init__(self, plugin_id: str) -> None:
                self.manifest = PluginManifest(plugin_id, plugin_id, "1.0.0")

            def start(self, context: PluginContext) -> Callable[[], None]:
                del context
                return lambda: stopped.append(self.manifest.plugin_id)

        manager = PluginManager(PluginContext(CapabilityRegistry().register))
        manager.start(OrderedPlugin("first"))
        manager.start(OrderedPlugin("second"))
        manager.stop_all()
        self.assertEqual(stopped, ["second", "first"])


class FakeMcpTransport:
    def __init__(self, result: McpCallResult) -> None:
        self.result = result
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    async def list_tools(self, server):
        return ()

    async def call_tool(self, server, tool_name, arguments):
        self.calls.append((server.server_id, tool_name, arguments))
        return self.result

    async def close(self):
        return None


class McpExtensionTests(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_tool_maps_capability_and_call(self) -> None:
        server = McpServerSpec("reverse", ("mcp-reverse",))
        spec = McpToolSpec("reverse", "strings")
        transport = FakeMcpTransport(McpCallResult("ELF strings"))
        tool = McpTool(server, spec, transport)

        result = await tool.execute(
            ToolRequest("mcp.reverse.strings", {"artifact": "sha256:abc"})
        )
        self.assertEqual(tool.capability, "mcp.reverse.strings")
        self.assertTrue(result.ok)
        self.assertEqual(
            transport.calls,
            [("reverse", "strings", {"artifact": "sha256:abc"})],
        )
