"""Composition helper for the default W2 middleware order."""

from xhunter.contracts.event_bus import EventBus
from xhunter.contracts.policy import PolicyEngine
from xhunter.orchestration.dispatcher import (
    AuditMiddleware,
    PolicyMiddleware,
    ToolDispatcher,
)
from xhunter.orchestration.policies import BudgetController
from xhunter.runtime.capability import CapabilityRegistry


def build_tool_dispatcher(
    registry: CapabilityRegistry,
    budget: BudgetController,
    policy: PolicyEngine,
    event_bus: EventBus,
) -> ToolDispatcher:
    return ToolDispatcher(
        registry.resolve,
        (
            budget.middleware,
            PolicyMiddleware(policy),
            AuditMiddleware(event_bus),
        ),
    )
