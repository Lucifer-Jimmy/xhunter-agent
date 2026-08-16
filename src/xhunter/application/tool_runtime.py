"""Composition helper for the default W2 middleware order."""

from xhunter.contracts.artifact import ArtifactStore
from xhunter.contracts.event_bus import EventBus
from xhunter.contracts.policy import PolicyEngine
from xhunter.contracts.storage import EvidenceRepository
from xhunter.orchestration.dispatcher import (
    AuditMiddleware,
    PolicyMiddleware,
    ToolDispatcher,
)
from xhunter.orchestration.dispatcher.evidence import EvidenceCaptureMiddleware
from xhunter.orchestration.policies import BudgetController
from xhunter.runtime.capability import CapabilityRegistry
from xhunter.services.redaction import Redactor


def build_tool_dispatcher(
    registry: CapabilityRegistry,
    budget: BudgetController,
    policy: PolicyEngine,
    event_bus: EventBus,
    evidence: EvidenceRepository | None = None,
    artifacts: ArtifactStore | None = None,
    redactor: Redactor | None = None,
) -> ToolDispatcher:
    middleware = [
        AuditMiddleware(event_bus),
        budget.middleware,
        PolicyMiddleware(policy),
    ]
    if (evidence is None) != (artifacts is None):
        raise ValueError("evidence and artifacts must be configured together")
    if evidence is not None and artifacts is not None:
        middleware.append(
            EvidenceCaptureMiddleware(
                evidence,
                artifacts,
                event_bus,
                redactor or Redactor(),
            )
        )
    return ToolDispatcher(
        registry.resolve,
        middleware,
    )
