"""Repository-owned Plugin API v1."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from xhunter.contracts.tool import Tool

PLUGIN_API_V1 = "1.0"


@dataclass(frozen=True, slots=True)
class PluginManifest:
    plugin_id: str
    name: str
    version: str
    api_version: str = PLUGIN_API_V1
    mandatory: bool = False

    def validate(self) -> None:
        if not self.plugin_id or not self.name or not self.version:
            raise ValueError("plugin id, name, and version must not be empty")
        if self.api_version.split(".", maxsplit=1)[0] != PLUGIN_API_V1.split(".")[0]:
            raise ValueError(f"incompatible Plugin API version: {self.api_version}")


@dataclass(frozen=True, slots=True)
class PluginContext:
    register_tool: Callable[[Tool], Callable[[], None]]


class BuiltinPlugin(Protocol):
    manifest: PluginManifest

    def start(self, context: PluginContext) -> Callable[[], None]:
        ...
