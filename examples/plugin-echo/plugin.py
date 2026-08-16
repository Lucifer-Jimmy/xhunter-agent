"""Example repository-owned Tool plugin."""

from collections.abc import Callable

from xhunter.contracts.plugin import PluginContext, PluginManifest
from xhunter.contracts.sandbox import Sandbox, SandboxRequest
from xhunter.contracts.tool import ToolRequest, ToolResult, ToolSpec


class EchoTool:
    capability = "example.echo"
    spec = ToolSpec(
        capability,
        "Echo text through the Sandbox Port.",
        {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    )

    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox

    async def execute(self, request: ToolRequest) -> ToolResult:
        text = request.arguments.get("text")
        if not isinstance(text, str):
            return ToolResult(ok=False, error="text must be a string")
        result = await self._sandbox.execute(SandboxRequest(("echo", text)))
        return ToolResult(result.exit_code == 0, result.stdout, result.stderr or None)


class EchoPlugin:
    manifest = PluginManifest("example.echo", "Example Echo", "1.0.0")

    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox

    def start(self, context: PluginContext) -> Callable[[], None]:
        return context.register_tool(EchoTool(self._sandbox))
