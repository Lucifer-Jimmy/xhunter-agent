"""Deterministic policy boundary for tool authorization."""

from dataclasses import dataclass
from typing import Protocol

from xhunter.contracts.tool import ToolRequest


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    reason: str = ""


class PolicyEngine(Protocol):
    async def authorize(self, request: ToolRequest) -> PolicyDecision:
        ...
