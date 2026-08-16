"""Explicit Mission loop; persistence and side effects stay in this service."""

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
            for task in decision.tasks:
                if task.mission_id != mission_id:
                    raise ValueError("planner returned a task for another mission")
                await self._tasks.save(task)
            pending = tuple(await self._tasks.list_pending(mission_id))
            scheduled = await self._scheduler.schedule(
                pending, ResourceState(active_tasks=0, max_concurrency=1)
            )
            task = scheduled.task
            if task is None:
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
                result = await self._agent.execute(self._context.build(mission, task))
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
            except Exception as exc:
                task.status = TaskStatus.TOOL_OUTCOME_UNKNOWN
                await self._tasks.save(task)
                await self._checkpoints.save(
                    checkpoint_key,
                    {
                        "mission_id": str(mission_id),
                        "task_id": str(task.id),
                        "status": task.status.value,
                        "error": str(exc),
                    },
                )
                await self._events.publish(
                    Event(
                        "task.recovery_required",
                        {"mission_id": str(mission_id), "task_id": str(task.id)},
                    )
                )
                failed += 1

        remaining = await self._tasks.list_pending(mission_id)
        if failed:
            mission.status = MissionStatus.FAILED
        elif remaining:
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

    async def _save_agent_evidence(
        self, mission: Mission, task: Task, content: str
    ) -> None:
        evidence = Evidence(
            id=EvidenceId(str(uuid4())),
            mission_id=mission.id,
            source=f"agent:{task.id}",
            content=content,
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
