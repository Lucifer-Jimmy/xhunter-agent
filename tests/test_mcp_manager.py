import unittest

from xhunter.adapters.mcp import FakeMcpTransport
from xhunter.contracts.mcp import McpCallResult, McpServerSpec, McpToolSpec
from xhunter.contracts.tool import ToolRequest
from xhunter.runtime.capability import CapabilityRegistry
from xhunter.runtime.mcp import McpServerManager


class McpServerManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovers_registers_calls_and_disposes_tools(self) -> None:
        registry = CapabilityRegistry()
        transport = FakeMcpTransport(
            (
                McpToolSpec(
                    "reverse",
                    "strings",
                    "Extract printable strings",
                    {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                    },
                ),
            ),
            lambda name, arguments: McpCallResult(
                f"{name}:{arguments['path']}"
            ),
        )
        manager = McpServerManager(registry, transport)
        capabilities = await manager.start(
            McpServerSpec("reverse", ("mcp-reverse",))
        )
        self.assertEqual(capabilities, ("mcp.reverse.strings",))
        tool = registry.resolve("mcp.reverse.strings")
        self.assertIsNotNone(tool)
        assert tool is not None
        result = await tool.execute(
            ToolRequest("mcp.reverse.strings", {"path": "challenge.bin"})
        )
        self.assertEqual(result.output, "strings:challenge.bin")

        await manager.stop()
        self.assertIsNone(registry.resolve("mcp.reverse.strings"))
        self.assertTrue(transport.closed)

    async def test_registration_failure_rolls_back_prior_tools(self) -> None:
        registry = CapabilityRegistry()
        existing_transport = FakeMcpTransport(
            (McpToolSpec("one", "same", input_schema={"type": "object"}),),
            lambda _name, _arguments: McpCallResult("ok"),
        )
        first = McpServerManager(registry, existing_transport)
        await first.start(McpServerSpec("one", ("server-one",)))

        transport = FakeMcpTransport(
            (
                McpToolSpec("two", "fresh", input_schema={"type": "object"}),
                McpToolSpec("one", "same", input_schema={"type": "object"}),
            ),
            lambda _name, _arguments: McpCallResult("ok"),
        )
        manager = McpServerManager(registry, transport)
        with self.assertRaises(ValueError):
            await manager.start(McpServerSpec("two", ("server-two",)))
        self.assertIsNone(registry.resolve("mcp.two.fresh"))
        self.assertTrue(transport.closed)
        await first.stop()

    async def test_rejects_tool_declared_for_another_server(self) -> None:
        registry = CapabilityRegistry()
        transport = FakeMcpTransport(
            (McpToolSpec("other", "tool", input_schema={"type": "object"}),),
            lambda _name, _arguments: McpCallResult("unused"),
        )
        with self.assertRaises(ValueError):
            await McpServerManager(registry, transport).start(
                McpServerSpec("expected", ("server",))
            )
        self.assertTrue(transport.closed)
