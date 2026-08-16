"""Single-purpose dispatcher middleware implementations."""

from dataclasses import dataclass

from xhunter.contracts.event_bus import Event, EventBus
from xhunter.contracts.policy import PolicyEngine
from xhunter.contracts.tool import ToolNext, ToolRequest, ToolResult


@dataclass(slots=True)
class PolicyMiddleware:
    engine: PolicyEngine

    async def __call__(
        self, request: ToolRequest, call_next: ToolNext
    ) -> ToolResult:
        decision = await self.engine.authorize(request)
        if not decision.allowed:
            return ToolResult.rejected_result(decision.reason or "policy denied")
        return await call_next(request)


@dataclass(slots=True)
class AuditMiddleware:
    event_bus: EventBus

    async def __call__(
        self, request: ToolRequest, call_next: ToolNext
    ) -> ToolResult:
        await self.event_bus.publish(
            Event(
                "tool.called",
                {
                    "mission_id": request.mission_id,
                    "task_id": request.task_id,
                    "capability": request.capability,
                },
            )
        )
        try:
            result = await call_next(request)
        except Exception as exc:
            await self.event_bus.publish(
                Event(
                    "tool.failed",
                    {
                        "mission_id": request.mission_id,
                        "task_id": request.task_id,
                        "capability": request.capability,
                        "error_type": type(exc).__name__,
                    },
                )
            )
            raise
        event_name = "tool.rejected" if result.rejected else "tool.completed"
        await self.event_bus.publish(
            Event(
                event_name,
                {
                    "mission_id": request.mission_id,
                    "task_id": request.task_id,
                    "capability": request.capability,
                    "ok": result.ok,
                },
            )
        )
        return result
