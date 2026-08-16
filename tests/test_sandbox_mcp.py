import json
import unittest

from xhunter.adapters.mcp import SandboxMcpTransport
from xhunter.adapters.memory import FakeSandbox
from xhunter.contracts.mcp import McpServerSpec
from xhunter.contracts.sandbox import SandboxResult


class SandboxMcpTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_lists_tools_through_sandbox_bridge(self) -> None:
        sandbox = FakeSandbox(
            SandboxResult(
                0,
                stdout=json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "result": {
                            "tools": [
                                {
                                    "name": "strings",
                                    "description": "Extract strings",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "path": {"type": "string"}
                                        },
                                    },
                                }
                            ]
                        },
                    }
                ),
            )
        )
        transport = SandboxMcpTransport(sandbox)
        tools = await transport.list_tools(
            McpServerSpec("reverse", ("mcp-reverse", "--stdio"))
        )
        envelope = json.loads(sandbox.requests[0].stdin or b"{}")
        self.assertEqual(tools[0].capability, "mcp.reverse.strings")
        self.assertEqual(envelope["method"], "tools/list")
        self.assertEqual(envelope["command"], ["mcp-reverse", "--stdio"])
        self.assertEqual(sandbox.requests[0].command[:3], ("python3", "-I", "-c"))

    async def test_calls_tool_and_normalizes_text_content(self) -> None:
        sandbox = FakeSandbox(
            SandboxResult(
                0,
                stdout=json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "result": {
                            "content": [
                                {"type": "text", "text": "first"},
                                {"type": "text", "text": "second"},
                            ],
                            "isError": False,
                        },
                    }
                ),
            )
        )
        result = await SandboxMcpTransport(sandbox).call_tool(
            McpServerSpec("reverse", ("server",)),
            "strings",
            {"path": "challenge.bin"},
        )
        envelope = json.loads(sandbox.requests[0].stdin or b"{}")
        self.assertEqual(result.content, "first\nsecond")
        self.assertEqual(envelope["params"]["name"], "strings")

    async def test_bridge_failure_is_structured_error(self) -> None:
        transport = SandboxMcpTransport(
            FakeSandbox(SandboxResult(1, stderr="server unavailable"))
        )
        with self.assertRaisesRegex(RuntimeError, "server unavailable"):
            await transport.list_tools(McpServerSpec("test", ("server",)))
