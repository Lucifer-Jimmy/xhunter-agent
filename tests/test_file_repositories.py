import asyncio
import tempfile
import unittest
from pathlib import Path

from xhunter.adapters.storage import (
    FileEvidenceRepository,
    FileMissionRepository,
    FileTaskRepository,
)
from xhunter.kernel.entities import Evidence, Mission, Task, TaskStatus
from xhunter.kernel.types import EvidenceId, MissionId, TaskId


class FileRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_entities_survive_repository_recreation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            mission = Mission(MissionId("m1"), "challenge", ("target.local",))
            task = Task(
                TaskId("t1"),
                mission.id,
                "inspect",
                ("network.http",),
                TaskStatus.RUNNING,
                10,
            )
            evidence = Evidence(EvidenceId("e1"), mission.id, "agent", "redacted")
            await FileMissionRepository(root).save(mission)
            await FileTaskRepository(root).save(task)
            await FileEvidenceRepository(root).save(evidence)

            restored_mission = await FileMissionRepository(root).get(mission.id)
            restored_task = await FileTaskRepository(root).get(task.id)
            evidence_file = (root / "evidence.json").read_text(encoding="utf-8")

        self.assertEqual(restored_mission, mission)
        self.assertEqual(restored_task, task)
        self.assertIn("redacted", evidence_file)

    async def test_concurrent_task_saves_preserve_all_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = FileTaskRepository(Path(temporary_directory))
            tasks = [
                Task(TaskId(f"t{index}"), MissionId("m1"), f"task {index}")
                for index in range(20)
            ]
            await asyncio.gather(*(repository.save(task) for task in tasks))
            restored = await repository.list_for_mission(MissionId("m1"))
        self.assertEqual({task.id for task in restored}, {task.id for task in tasks})

    async def test_pending_query_filters_mission_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = FileTaskRepository(Path(temporary_directory))
            pending = Task(TaskId("pending"), MissionId("m1"), "pending")
            completed = Task(
                TaskId("done"),
                MissionId("m1"),
                "done",
                status=TaskStatus.COMPLETED,
            )
            foreign = Task(TaskId("foreign"), MissionId("m2"), "foreign")
            for task in (pending, completed, foreign):
                await repository.save(task)
            result = await repository.list_pending(MissionId("m1"))
        self.assertEqual([task.id for task in result], [pending.id])
