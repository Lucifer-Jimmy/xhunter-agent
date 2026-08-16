"""Start and stop repository-owned plugins with reverse-order disposal."""

from collections.abc import Callable
from dataclasses import dataclass

from xhunter.contracts.plugin import BuiltinPlugin, PluginContext


@dataclass(frozen=True, slots=True)
class PluginFailure:
    plugin_id: str
    reason: str


class PluginManager:
    def __init__(self, context: PluginContext) -> None:
        self._context = context
        self._disposers: list[tuple[str, Callable[[], None]]] = []

    def start(self, plugin: BuiltinPlugin) -> PluginFailure | None:
        plugin.manifest.validate()
        try:
            disposer = plugin.start(self._context)
        except Exception as exc:
            if plugin.manifest.mandatory:
                raise
            return PluginFailure(plugin.manifest.plugin_id, str(exc))
        self._disposers.append((plugin.manifest.plugin_id, disposer))
        return None

    def stop_all(self) -> None:
        while self._disposers:
            _plugin_id, disposer = self._disposers.pop()
            disposer()
