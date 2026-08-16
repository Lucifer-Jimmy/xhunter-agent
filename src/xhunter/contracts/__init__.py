"""Cross-module contracts and transport DTOs."""

from xhunter.contracts.agent_executor import AgentExecutor
from xhunter.contracts.artifact import ArtifactStore
from xhunter.contracts.context import ContextProvider
from xhunter.contracts.mcp import McpTransport
from xhunter.contracts.model import ModelProvider, ModelRequest, ModelResponse
from xhunter.contracts.planning import Planner, Scheduler
from xhunter.contracts.plugin import BuiltinPlugin
from xhunter.contracts.tool import Tool, ToolRequest, ToolResult
from xhunter.contracts.verification import Verifier

__all__ = [
    "AgentExecutor",
    "ArtifactStore",
    "BuiltinPlugin",
    "ContextProvider",
    "McpTransport",
    "Planner",
    "Scheduler",
    "Verifier",
    "ModelProvider",
    "ModelRequest",
    "ModelResponse",
    "Tool",
    "ToolRequest",
    "ToolResult",
]
