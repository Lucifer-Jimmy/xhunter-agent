"""Python capability implemented exclusively through the Sandbox Port."""

import sys

from xhunter.contracts.sandbox import Sandbox, SandboxRequest
from xhunter.contracts.tool import ToolRequest, ToolResult


class PythonTool:
    capability = "code.python"

    def __init__(self, sandbox: Sandbox, executable: str | None = None) -> None:
        self._sandbox = sandbox
        self._executable = executable or sys.executable

    async def execute(self, request: ToolRequest) -> ToolResult:
        code = request.arguments.get("code")
        if not isinstance(code, str) or not code:
            return ToolResult(ok=False, error="code must be a non-empty string")

        timeout = request.arguments.get("timeout_seconds", 30.0)
        if not isinstance(timeout, int | float):
            return ToolResult(ok=False, error="timeout_seconds must be numeric")
        working_directory = request.arguments.get("working_directory")
        if working_directory is not None and not isinstance(working_directory, str):
            return ToolResult(ok=False, error="working_directory must be a string")

        result = await self._sandbox.execute(
            SandboxRequest(
                command=(self._executable, "-I", "-c", code),
                timeout_seconds=float(timeout),
                working_directory=working_directory,
            )
        )
        return ToolResult(
            ok=result.exit_code == 0,
            output=result.stdout,
            error=result.stderr or None,
        )
