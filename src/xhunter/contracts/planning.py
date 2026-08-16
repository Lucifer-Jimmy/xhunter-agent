"""Planner and scheduler contracts."""

from dataclasses import dataclass
from typing import Protocol

from xhunter.kernel.entities import Task


@dataclass(frozen=True, slots=True)
class PlanningContext:
    mission_id: str
    mission_name: str
    scope: tuple[str, ...] = ()
    observations: tuple[str, ...] = ()
    pending_tasks: tuple[Task, ...] = ()


@dataclass(frozen=True, slots=True)
class PlanningDecision:
    tasks: tuple[Task, ...] = ()
    rationale: str = ""


class Planner(Protocol):
    async def plan(self, context: PlanningContext) -> PlanningDecision:
        ...


@dataclass(frozen=True, slots=True)
class ResourceState:
    active_tasks: int = 0
    max_concurrency: int = 1


@dataclass(frozen=True, slots=True)
class SchedulingDecision:
    task: Task | None = None


class Scheduler(Protocol):
    async def schedule(
        self, tasks: tuple[Task, ...], resources: ResourceState
    ) -> SchedulingDecision:
        ...
