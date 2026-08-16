"""Apply Planner decisions through validation, deduplication, and persistence."""

from dataclasses import dataclass

from xhunter.contracts.event_bus import Event, EventBus
from xhunter.contracts.planning import PlanningDecision
from xhunter.contracts.storage import TaskRepository
from xhunter.kernel.entities import Task
from xhunter.kernel.types import MissionId


@dataclass(frozen=True, slots=True)
class PlanningApplyResult:
    created: tuple[Task, ...]
    duplicate_count: int


class PlanningService:
    def __init__(self, tasks: TaskRepository, events: EventBus) -> None:
        self._tasks = tasks
        self._events = events

    async def apply(
        self, mission_id: MissionId, decision: PlanningDecision
    ) -> PlanningApplyResult:
        existing = await self._tasks.list_for_mission(mission_id)
        keys = {_dedup_key(task) for task in existing}
        created: list[Task] = []
        duplicates = 0
        for task in decision.tasks:
            self._validate(mission_id, task)
            key = _dedup_key(task)
            if key in keys:
                duplicates += 1
                continue
            await self._tasks.save(task)
            keys.add(key)
            created.append(task)
            await self._events.publish(
                Event(
                    "task.created",
                    {
                        "mission_id": str(mission_id),
                        "task_id": str(task.id),
                        "priority": task.priority,
                    },
                )
            )
        return PlanningApplyResult(tuple(created), duplicates)

    def _validate(self, mission_id: MissionId, task: Task) -> None:
        if task.mission_id != mission_id:
            raise ValueError("planner returned a task for another mission")
        if not task.objective.strip():
            raise ValueError("planned task objective must not be empty")
        if any(not capability.strip() for capability in task.required_capabilities):
            raise ValueError("planned task capabilities must not be empty")


def _dedup_key(task: Task) -> tuple[str, tuple[str, ...]]:
    return (
        task.objective.strip().casefold(),
        tuple(sorted(task.required_capabilities)),
    )
