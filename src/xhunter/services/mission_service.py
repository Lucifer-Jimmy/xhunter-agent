"""Explicit Mission loop; persistence and side effects stay in this service."""

import asyncio
from dataclasses import dataclass
from uuid import uuid4

from xhunter.contracts.agent_executor import AgentExecutor
from xhunter.contracts.checkpoint import CheckpointStore
from xhunter.contracts.context import ContextProvider
from xhunter.contracts.event_bus import Event, EventBus
from xhunter.contracts.planning import (
    Planner,
    PlanningContext,
    ResourceState,
    Scheduler,
)
from xhunter.contracts.storage import (
    EvidenceRepository,
    MissionRepository,
    TaskRepository,
)
from xhunter.contracts.verification import VerificationContext, Verifier
from xhunter.kernel.entities import (
    Evidence,
    Mission,
    MissionStatus,
    Task,
    TaskStatus,
)
from xhunter.kernel.types import EvidenceId, MissionId
from xhunter.services.planning_service import PlanningService
from xhunter.services.redaction import Redactor
from xhunter.services.task_lease import TaskLeaseManager, run_with_lease_heartbeat


@dataclass(frozen=True, slots=True)
class MissionRunResult:
    mission_id: MissionId
    completed_tasks: int
    failed_tasks: int


class MissionService:
    def __init__(
        self,
        missions: MissionRepository,
        tasks: TaskRepository,
        evidence: EvidenceRepository,
        checkpoints: CheckpointStore,
        events: EventBus,
        planner: Planner,
        scheduler: Scheduler,
        context: ContextProvider,
        agent: AgentExecutor,
        verifier: Verifier,
        redactor: Redactor | None = None,
        leases: TaskLeaseManager | None = None,
        worker_id: str = "mission-service",
        lease_ttl_seconds: float = 60.0,
        planning_service: PlanningService | None = None,
    ) -> None:
        self._missions = missions
        self._tasks = tasks
        self._evidence = evidence
        self._checkpoints = checkpoints
        self._events = events
        self._planner = planner
        self._scheduler = scheduler
        self._context = context
        self._agent = agent
        self._verifier = verifier
        self._redactor = redactor or Redactor()
        self._leases = leases or TaskLeaseManager()
        self._worker_id = worker_id
        self._lease_ttl_seconds = lease_ttl_seconds
        self._planning_service = planning_service or PlanningService(tasks, events)

    async def run(
        self, mission_id: MissionId, max_tasks: int = 100
    ) -> MissionRunResult:
        if max_tasks <= 0:
            raise ValueError("max_tasks must be positive")
        mission = await self._missions.get(mission_id)
        if mission is None:
            raise KeyError(f"mission not found: {mission_id}")
        mission.status = MissionStatus.RUNNING
        await self._missions.save(mission)
        await self._events.publish(
            Event("mission.started", {"mission_id": str(mission_id)})
        )

        completed = 0
        failed = 0
        for _ in range(max_tasks):
            pending = tuple(await self._tasks.list_pending(mission_id))
            decision = await self._planner.plan(
                PlanningContext(
                    mission_id=str(mission.id),
                    mission_name=mission.name,
                    scope=mission.scope,
                    pending_tasks=pending,
                )
            )
            await self._planning_service.apply(mission_id, decision)
            pending = tuple(await self._tasks.list_pending(mission_id))
            scheduled = await self._scheduler.schedule(
                pending, ResourceState(active_tasks=0, max_concurrency=1)
            )
            task = scheduled.task
            if task is None:
                break
            acquired = await self._leases.acquire(
                task.id, self._worker_id, self._lease_ttl_seconds
            )
            if not acquired:
                break

            task.status = TaskStatus.RUNNING
            await self._tasks.save(task)
            checkpoint_key = _checkpoint_key(task)
            await self._checkpoints.save(
                checkpoint_key,
                {
                    "mission_id": str(mission_id),
                    "task_id": str(task.id),
                    "status": task.status.value,
                },
            )
            try:
                operation = asyncio.create_task(
                    self._agent.execute(self._context.build(mission, task))
                )
                result = await run_with_lease_heartbeat(
                    operation,
                    self._leases,
                    task.id,
                    self._worker_id,
                    self._lease_ttl_seconds,
                )
                await self._save_agent_evidence(mission, task, result.content)
                verification = await self._verifier.verify(
                    result,
                    VerificationContext(str(mission_id), str(task.id)),
                )
                task.status = (
                    TaskStatus.COMPLETED if verification.accepted else TaskStatus.FAILED
                )
                await self._tasks.save(task)
                await self._events.publish(
                    Event(
                        "task.completed" if verification.accepted else "task.failed",
                        {
                            "mission_id": str(mission_id),
                            "task_id": str(task.id),
                            "reason": verification.reason,
                        },
                    )
                )
                await self._checkpoints.delete(checkpoint_key)
                completed += int(verification.accepted)
                failed += int(not verification.accepted)
            except asyncio.CancelledError:
                await self._mark_unknown_outcome(
                    mission_id, task, checkpoint_key, "CancelledError"
                )
                raise
            except Exception as exc:
                await self._mark_unknown_outcome(
                    mission_id, task, checkpoint_key, type(exc).__name__
                )
                failed += 1
            finally:
                await self._leases.release(task.id, self._worker_id)

        all_tasks = await self._tasks.list_for_mission(mission_id)
        has_failed = any(
            task.status in {TaskStatus.FAILED, TaskStatus.TOOL_OUTCOME_UNKNOWN}
            for task in all_tasks
        )
        has_incomplete = any(
            task.status in {TaskStatus.PENDING, TaskStatus.RUNNING}
            for task in all_tasks
        )
        if failed or has_failed:
            mission.status = MissionStatus.FAILED
        elif has_incomplete:
            mission.status = MissionStatus.RUNNING
        else:
            mission.status = MissionStatus.COMPLETED
        await self._missions.save(mission)
        await self._events.publish(
            Event(
                "mission.completed",
                {
                    "mission_id": str(mission_id),
                    "failed": failed,
                    "status": mission.status.value,
                },
            )
        )
        return MissionRunResult(mission_id, completed, failed)

    async def _mark_unknown_outcome(
        self,
        mission_id: MissionId,
        task: Task,
        checkpoint_key: str,
        error_type: str,
    ) -> None:
        task.status = TaskStatus.TOOL_OUTCOME_UNKNOWN
        await self._tasks.save(task)
        await self._checkpoints.save(
            checkpoint_key,
            {
                "mission_id": str(mission_id),
                "task_id": str(task.id),
                "status": task.status.value,
                "error_type": error_type,
            },
        )
        await self._events.publish(
            Event(
                "task.recovery_required",
                {"mission_id": str(mission_id), "task_id": str(task.id)},
            )
        )

    async def _save_agent_evidence(
        self, mission: Mission, task: Task, content: str
    ) -> None:
        evidence = Evidence(
            id=EvidenceId(str(uuid4())),
            mission_id=mission.id,
            source=f"agent:{task.id}",
            content=self._redactor.redact(content).text,
        )
        await self._evidence.save(evidence)
        await self._events.publish(
            Event(
                "evidence.created",
                {
                    "mission_id": str(mission.id),
                    "evidence_id": str(evidence.id),
                },
            )
        )


def _checkpoint_key(task: Task) -> str:
    return f"task:{task.id}"
