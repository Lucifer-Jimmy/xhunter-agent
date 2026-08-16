"""Cross-module contracts and transport DTOs."""

from xhunter.contracts.agent_executor import AgentExecutor
from xhunter.contracts.artifact import ArtifactStore
from xhunter.contracts.mcp import McpTransport
from xhunter.contracts.model import ModelProvider, ModelRequest, ModelResponse
from xhunter.contracts.plugin import BuiltinPlugin
from xhunter.contracts.tool import Tool, ToolRequest, ToolResult

__all__ = [
    "AgentExecutor",
    "ArtifactStore",
    "BuiltinPlugin",
    "McpTransport",
    "ModelProvider",
    "ModelRequest",
    "ModelResponse",
    "Tool",
    "ToolRequest",
    "ToolResult",
]
