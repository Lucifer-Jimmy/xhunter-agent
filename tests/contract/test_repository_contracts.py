import tempfile
from pathlib import Path

import pytest

from xhunter.adapters.memory import MemoryMissionRepository, MemoryTaskRepository
from xhunter.adapters.storage import FileMissionRepository, FileTaskRepository
from xhunter.kernel.entities import Mission, Task, TaskStatus
from xhunter.kernel.types import MissionId, TaskId


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["memory", "file"])
async def test_mission_repository_contract(provider: str) -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        repository = (
            MemoryMissionRepository()
            if provider == "memory"
            else FileMissionRepository(Path(temporary_directory))
        )
        mission = Mission(MissionId("m1"), "contract", ("target.local",))
        assert await repository.get(mission.id) is None
        await repository.save(mission)
        restored = await repository.get(mission.id)
    assert restored == mission


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["memory", "file"])
async def test_task_repository_contract(provider: str) -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        repository = (
            MemoryTaskRepository()
            if provider == "memory"
            else FileTaskRepository(Path(temporary_directory))
        )
        pending = Task(TaskId("pending"), MissionId("m1"), "pending")
        done = Task(
            TaskId("done"),
            MissionId("m1"),
            "done",
            status=TaskStatus.COMPLETED,
        )
        await repository.save(pending)
        await repository.save(done)
        restored = await repository.get(pending.id)
        pending_tasks = await repository.list_pending(MissionId("m1"))
        all_tasks = await repository.list_for_mission(MissionId("m1"))
    assert restored == pending
    assert [task.id for task in pending_tasks] == [pending.id]
    assert {task.id for task in all_tasks} == {pending.id, done.id}
