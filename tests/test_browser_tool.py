import json
import unittest

from xhunter.adapters.memory import FakeSandbox
from xhunter.contracts.plugin import PluginContext
from xhunter.contracts.sandbox import SandboxResult
from xhunter.contracts.tool import ToolRequest
from xhunter.plugins.builtin import BrowserTool, CoreToolsPlugin
from xhunter.runtime.capability import CapabilityRegistry
from xhunter.runtime.plugin import PluginManager


class BrowserToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_browser_actions_are_delegated_to_sandbox_stdin(self) -> None:
        sandbox = FakeSandbox(SandboxResult(0, stdout="<html>ok</html>"))
        result = await BrowserTool(sandbox).execute(
            ToolRequest(
                "browser.web",
                {
                    "url": "http://challenge.local/login",
                    "actions": [
                        {
                            "operation": "fill",
                            "selector": "#username",
                            "value": "admin",
                        },
                        {"operation": "click", "selector": "button"},
                    ],
                },
            )
        )
        sandbox_request = sandbox.requests[0]
        payload = json.loads(sandbox_request.stdin or b"{}")
        self.assertTrue(result.ok)
        self.assertEqual(sandbox_request.command[:3], ("python3", "-I", "-c"))
        self.assertEqual(payload["actions"][0]["value"], "admin")

    async def test_invalid_fill_without_value_is_rejected_before_sandbox(self) -> None:
        sandbox = FakeSandbox()
        result = await BrowserTool(sandbox).execute(
            ToolRequest(
                "browser.web",
                {
                    "url": "http://challenge.local",
                    "actions": [{"operation": "fill", "selector": "#name"}],
                },
            )
        )
        self.assertFalse(result.ok)
        self.assertEqual(sandbox.requests, [])

    async def test_core_plugin_registers_and_disposes_browser_capability(self) -> None:
        registry = CapabilityRegistry()
        manager = PluginManager(PluginContext(registry.register))
        manager.start(CoreToolsPlugin(FakeSandbox()))
        self.assertIsNotNone(registry.resolve("browser.web"))
        manager.stop_all()
        self.assertIsNone(registry.resolve("browser.web"))
