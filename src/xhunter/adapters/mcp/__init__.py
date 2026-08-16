"""MCP adapters used for tests and future sandbox supervisors."""

from xhunter.adapters.mcp.fake import FakeMcpTransport
from xhunter.adapters.mcp.sandbox import SandboxMcpTransport

__all__ = ["FakeMcpTransport", "SandboxMcpTransport"]
