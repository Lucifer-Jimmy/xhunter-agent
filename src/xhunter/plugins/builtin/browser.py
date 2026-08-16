"""Browser automation executed by Playwright inside the mission sandbox."""

import json

from xhunter.contracts.sandbox import Sandbox, SandboxRequest
from xhunter.contracts.tool import ToolRequest, ToolResult, ToolSpec

_BROWSER_HELPER = """
import asyncio
import json
import sys

async_playwright = getattr(
    __import__("playwright.async_api", fromlist=["async_playwright"]),
    "async_playwright",
)

async def main():
    request = json.load(sys.stdin)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(request["url"], wait_until="domcontentloaded")
        for action in request.get("actions", []):
            operation = action["operation"]
            if operation == "click":
                await page.locator(action["selector"]).click()
            elif operation == "fill":
                await page.locator(action["selector"]).fill(action["value"])
            else:
                raise ValueError(f"unsupported browser action: {operation}")
        if request["output"] == "content":
            print(await page.content())
        else:
            await page.screenshot(path=request["screenshot_path"], full_page=True)
            print(json.dumps({"screenshot_path": request["screenshot_path"]}))
        await browser.close()

asyncio.run(main())
""".strip()


class BrowserTool:
    capability = "browser.web"
    spec = ToolSpec(
        capability,
        "Navigate and interact with a web page in the mission sandbox.",
        {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "operation": {"type": "string", "enum": ["click", "fill"]},
                            "selector": {"type": "string"},
                            "value": {"type": "string"},
                        },
                        "required": ["operation", "selector"],
                    },
                },
                "output": {"type": "string", "enum": ["content", "screenshot"]},
                "screenshot_path": {"type": "string"},
                "timeout_seconds": {"type": "number"},
            },
            "required": ["url"],
        },
    )

    def __init__(self, sandbox: Sandbox, executable: str = "python3") -> None:
        self._sandbox = sandbox
        self._executable = executable

    async def execute(self, request: ToolRequest) -> ToolResult:
        url = request.arguments.get("url")
        if not isinstance(url, str) or not url:
            return ToolResult(ok=False, error="url must be a non-empty string")
        actions = _actions(request.arguments.get("actions", []))
        if actions is None:
            return ToolResult(ok=False, error="actions are invalid")
        output = request.arguments.get("output", "content")
        if output not in {"content", "screenshot"}:
            return ToolResult(ok=False, error="output must be content or screenshot")
        screenshot_path = request.arguments.get(
            "screenshot_path", "browser-screenshot.png"
        )
        if not isinstance(screenshot_path, str) or not screenshot_path:
            return ToolResult(ok=False, error="screenshot_path must be a string")
        timeout = request.arguments.get("timeout_seconds", 60.0)
        if not isinstance(timeout, int | float) or timeout <= 0:
            return ToolResult(ok=False, error="timeout_seconds must be positive")

        payload = {
            "url": url,
            "actions": actions,
            "output": output,
            "screenshot_path": screenshot_path,
        }
        result = await self._sandbox.execute(
            SandboxRequest(
                command=(self._executable, "-I", "-c", _BROWSER_HELPER),
                stdin=json.dumps(payload).encode(),
                timeout_seconds=float(timeout),
            )
        )
        return ToolResult(
            ok=result.exit_code == 0,
            output=result.stdout,
            error=result.stderr or None,
        )


def _actions(value: object) -> list[dict[str, str]] | None:
    if not isinstance(value, list):
        return None
    actions: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            return None
        operation = item.get("operation")
        selector = item.get("selector")
        action_value = item.get("value")
        if operation not in {"click", "fill"} or not isinstance(selector, str):
            return None
        if operation == "fill" and not isinstance(action_value, str):
            return None
        action = {"operation": operation, "selector": selector}
        if isinstance(action_value, str):
            action["value"] = action_value
        actions.append(action)
    return actions
