"""Deterministic priority scheduler."""

from xhunter.contracts.planning import (
    ResourceState,
    SchedulingDecision,
)
from xhunter.kernel.entities import Task


class PriorityScheduler:
    async def schedule(
        self, tasks: tuple[Task, ...], resources: ResourceState
    ) -> SchedulingDecision:
        if resources.active_tasks >= resources.max_concurrency or not tasks:
            return SchedulingDecision()
        return SchedulingDecision(task=max(tasks, key=lambda task: task.priority))
