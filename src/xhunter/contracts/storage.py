"""Repository and artifact contracts."""

from typing import Protocol

from xhunter.kernel.entities import Evidence, Mission, Task
from xhunter.kernel.types import MissionId, TaskId


class MissionRepository(Protocol):
    async def save(self, mission: Mission) -> None:
        ...

    async def get(self, mission_id: MissionId) -> Mission | None:
        ...


class TaskRepository(Protocol):
    async def save(self, task: Task) -> None:
        ...

    async def get(self, task_id: TaskId) -> Task | None:
        ...

    async def list_pending(self, mission_id: MissionId) -> list[Task]:
        ...

    async def list_for_mission(self, mission_id: MissionId) -> list[Task]:
        ...


class EvidenceRepository(Protocol):
    async def save(self, evidence: Evidence) -> None:
        ...
