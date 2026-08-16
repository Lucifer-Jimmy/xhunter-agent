"""HTTP capability executed by curl inside the mission sandbox."""

from xhunter.contracts.sandbox import Sandbox, SandboxRequest
from xhunter.contracts.tool import ToolRequest, ToolResult, ToolSpec


class HttpTool:
    capability = "network.http"
    spec = ToolSpec(
        capability=capability,
        description="Send an HTTP request from the mission sandbox.",
        input_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "method": {"type": "string"},
                "headers": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
                "body": {"type": "string"},
                "timeout_seconds": {"type": "number"},
            },
            "required": ["url"],
        },
    )

    def __init__(self, sandbox: Sandbox, executable: str = "curl") -> None:
        self._sandbox = sandbox
        self._executable = executable

    async def execute(self, request: ToolRequest) -> ToolResult:
        url = request.arguments.get("url")
        if not isinstance(url, str) or not url:
            return ToolResult(ok=False, error="url must be a non-empty string")
        method = request.arguments.get("method", "GET")
        if not isinstance(method, str) or not method:
            return ToolResult(ok=False, error="method must be a non-empty string")
        timeout = request.arguments.get("timeout_seconds", 30.0)
        if not isinstance(timeout, int | float) or timeout <= 0:
            return ToolResult(ok=False, error="timeout_seconds must be positive")
        headers = _headers(request.arguments.get("headers", {}))
        if headers is None:
            return ToolResult(ok=False, error="headers must map strings to strings")
        body = request.arguments.get("body")
        if body is not None and not isinstance(body, str):
            return ToolResult(ok=False, error="body must be a string")

        command = [
            self._executable,
            "--silent",
            "--show-error",
            "--include",
            "--request",
            method.upper(),
            "--max-time",
            str(float(timeout)),
        ]
        for name, value in headers:
            command.extend(("--header", f"{name}: {value}"))
        if body is not None:
            command.extend(("--data-binary", "@-"))
        command.append(url)

        result = await self._sandbox.execute(
            SandboxRequest(
                command=tuple(command),
                timeout_seconds=float(timeout) + 1,
                stdin=body.encode() if body is not None else None,
            )
        )
        return ToolResult(
            ok=result.exit_code == 0,
            output=result.stdout,
            error=result.stderr or None,
        )


def _headers(value: object) -> tuple[tuple[str, str], ...] | None:
    if not isinstance(value, dict):
        return None
    if not all(
        isinstance(name, str) and isinstance(item, str)
        for name, item in value.items()
    ):
        return None
    return tuple(value.items())
