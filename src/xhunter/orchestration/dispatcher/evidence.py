"""Redact, persist, and spill Tool observations after sandbox execution."""

from dataclasses import dataclass
from uuid import uuid4

from xhunter.contracts.artifact import ArtifactStore
from xhunter.contracts.event_bus import Event, EventBus
from xhunter.contracts.storage import EvidenceRepository
from xhunter.contracts.tool import ToolNext, ToolRequest, ToolResult
from xhunter.kernel.entities import Evidence
from xhunter.kernel.types import EvidenceId, MissionId
from xhunter.services.redaction import Redactor


@dataclass(slots=True)
class EvidenceCaptureMiddleware:
    evidence: EvidenceRepository
    artifacts: ArtifactStore
    events: EventBus
    redactor: Redactor
    spill_threshold: int = 16_384

    async def __call__(
        self, request: ToolRequest, call_next: ToolNext
    ) -> ToolResult:
        result = await call_next(request)
        raw = result.output if result.ok else (result.error or "")
        redacted = self.redactor.redact(raw)
        persisted = redacted.text
        if len(persisted.encode()) > self.spill_threshold:
            artifact = await self.artifacts.put(
                persisted.encode(),
                {
                    "mission_id": request.mission_id,
                    "task_id": request.task_id,
                    "capability": request.capability,
                },
            )
            persisted = f"artifact:{artifact.artifact_id}"

        evidence = Evidence(
            EvidenceId(str(uuid4())),
            MissionId(request.mission_id),
            f"tool:{request.capability}",
            persisted,
        )
        await self.evidence.save(evidence)
        await self.events.publish(
            Event(
                "evidence.created",
                {
                    "mission_id": request.mission_id,
                    "task_id": request.task_id,
                    "evidence_id": str(evidence.id),
                    "references": redacted.references,
                },
            )
        )
        sanitized = redacted.text
        return ToolResult(
            ok=result.ok,
            output=sanitized if result.ok else "",
            error=sanitized if not result.ok else None,
            rejected=result.rejected,
        )
