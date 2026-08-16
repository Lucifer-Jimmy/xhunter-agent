"""Filesystem capability executed by a Python helper inside the sandbox."""

import json

from xhunter.contracts.sandbox import Sandbox, SandboxRequest
from xhunter.contracts.tool import ToolRequest, ToolResult, ToolSpec

_HELPER = """
import json
import pathlib
import sys

request = json.load(sys.stdin)
operation = request["operation"]
path = pathlib.Path(request["path"])
if operation == "read":
    sys.stdout.write(path.read_text(encoding="utf-8"))
elif operation == "write":
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(request["content"], encoding="utf-8")
    print(json.dumps({"written": len(request["content"])}))
elif operation == "list":
    print(json.dumps(sorted(item.name for item in path.iterdir())))
else:
    raise ValueError(f"unsupported operation: {operation}")
""".strip()


class FilesystemTool:
    capability = "filesystem.workspace"
    spec = ToolSpec(
        capability=capability,
        description="Read, write, or list files in the sandbox workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["read", "write", "list"]},
                "path": {"type": "string"},
                "content": {"type": "string"},
                "timeout_seconds": {"type": "number"},
            },
            "required": ["operation", "path"],
        },
    )

    def __init__(self, sandbox: Sandbox, executable: str = "python3") -> None:
        self._sandbox = sandbox
        self._executable = executable

    async def execute(self, request: ToolRequest) -> ToolResult:
        operation = request.arguments.get("operation")
        path = request.arguments.get("path")
        if operation not in {"read", "write", "list"}:
            return ToolResult(ok=False, error="operation must be read, write, or list")
        if not isinstance(path, str) or not path:
            return ToolResult(ok=False, error="path must be a non-empty string")
        content = request.arguments.get("content")
        if operation == "write" and not isinstance(content, str):
            return ToolResult(ok=False, error="write requires string content")
        timeout = request.arguments.get("timeout_seconds", 30.0)
        if not isinstance(timeout, int | float) or timeout <= 0:
            return ToolResult(ok=False, error="timeout_seconds must be positive")

        payload: dict[str, object] = {"operation": operation, "path": path}
        if content is not None:
            payload["content"] = content
        result = await self._sandbox.execute(
            SandboxRequest(
                command=(self._executable, "-I", "-c", _HELPER),
                timeout_seconds=float(timeout),
                stdin=json.dumps(payload).encode(),
            )
        )
        return ToolResult(
            ok=result.exit_code == 0,
            output=result.stdout,
            error=result.stderr or None,
        )
