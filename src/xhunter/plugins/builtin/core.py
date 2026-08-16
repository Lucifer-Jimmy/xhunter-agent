"""Built-in shell and Python Tool plugin."""

from collections.abc import Callable

from xhunter.contracts.plugin import PluginContext, PluginManifest
from xhunter.contracts.sandbox import Sandbox
from xhunter.plugins.builtin.python_tool import PythonTool
from xhunter.plugins.builtin.shell import ShellTool


class CoreToolsPlugin:
    manifest = PluginManifest(
        plugin_id="xhunter.core-tools",
        name="Core Tools",
        version="0.1.0",
    )

    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox

    def start(self, context: PluginContext) -> Callable[[], None]:
        disposers = [
            context.register_tool(ShellTool(self._sandbox)),
            context.register_tool(PythonTool(self._sandbox)),
        ]

        def dispose() -> None:
            for disposer in reversed(disposers):
                disposer()

        return dispose
