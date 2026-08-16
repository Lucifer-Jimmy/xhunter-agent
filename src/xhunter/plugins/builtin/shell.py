"""Shell capability implemented exclusively through the Sandbox Port."""

from collections.abc import Sequence

from xhunter.contracts.sandbox import Sandbox, SandboxRequest
from xhunter.contracts.tool import ToolRequest, ToolResult, ToolSpec


class ShellTool:
    capability = "system.shell"
    spec = ToolSpec(
        capability=capability,
        description="Execute an argument-vector command in the mission sandbox.",
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "array", "items": {"type": "string"}},
                "timeout_seconds": {"type": "number"},
                "working_directory": {"type": "string"},
            },
            "required": ["command"],
        },
    )

    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox

    async def execute(self, request: ToolRequest) -> ToolResult:
        command = _string_sequence(request.arguments.get("command"))
        if not command:
            return ToolResult(ok=False, error="command must be a non-empty string list")

        timeout = request.arguments.get("timeout_seconds", 30.0)
        if not isinstance(timeout, int | float):
            return ToolResult(ok=False, error="timeout_seconds must be numeric")
        working_directory = request.arguments.get("working_directory")
        if working_directory is not None and not isinstance(working_directory, str):
            return ToolResult(ok=False, error="working_directory must be a string")

        result = await self._sandbox.execute(
            SandboxRequest(
                command=command,
                timeout_seconds=float(timeout),
                working_directory=working_directory,
            )
        )
        return ToolResult(
            ok=result.exit_code == 0,
            output=result.stdout,
            error=result.stderr or None,
        )


def _string_sequence(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    if not all(isinstance(item, str) for item in value):
        return ()
    return tuple(value)
