"""Explicit recovery decisions for tasks with unknown Tool outcomes."""

from enum import StrEnum

from xhunter.contracts.checkpoint import CheckpointStore
from xhunter.contracts.event_bus import Event, EventBus
from xhunter.contracts.storage import TaskRepository
from xhunter.kernel.entities import TaskStatus
from xhunter.kernel.types import TaskId


class RecoveryDecision(StrEnum):
    RETRY = "retry"
    FAIL = "fail"


class RecoveryService:
    def __init__(
        self,
        tasks: TaskRepository,
        checkpoints: CheckpointStore,
        events: EventBus,
    ) -> None:
        self._tasks = tasks
        self._checkpoints = checkpoints
        self._events = events

    async def resolve(self, task_id: TaskId, decision: RecoveryDecision) -> None:
        task = await self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"task not found: {task_id}")
        if task.status != TaskStatus.TOOL_OUTCOME_UNKNOWN:
            raise ValueError("only unknown-outcome tasks can be recovered")
        task.status = (
            TaskStatus.PENDING
            if decision == RecoveryDecision.RETRY
            else TaskStatus.FAILED
        )
        await self._tasks.save(task)
        await self._checkpoints.delete(f"task:{task.id}")
        await self._events.publish(
            Event(
                "task.recovered",
                {"task_id": str(task.id), "decision": decision.value},
            )
        )
