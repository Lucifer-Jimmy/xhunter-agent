import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from xhunter.adapters.checkpoint import FileCheckpointStore
from xhunter.adapters.memory import FakeModelProvider, InProcessEventBus
from xhunter.adapters.storage import FileMissionRepository, FileTaskRepository
from xhunter.application.config import load_config
from xhunter.application.resume_ctf import resume_ctf
from xhunter.contracts.model import ModelResponse
from xhunter.kernel.entities import Mission, Task, TaskStatus
from xhunter.kernel.types import MissionId, TaskId
from xhunter.services import RecoveryDecision, RecoveryService


class ResumeCtfTests(unittest.IsolatedAsyncioTestCase):
    async def test_recover_retry_then_resume_completes_persisted_mission(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            config = replace(
                load_config(environment={}),
                allowed_targets=("challenge.local",),
                trace_path=root / "trace.jsonl",
                artifacts_path=root / "artifacts",
                checkpoint_path=root / "checkpoints",
                storage_path=root / "storage",
            )
            missions = FileMissionRepository(config.storage_path)
            tasks = FileTaskRepository(config.storage_path)
            checkpoints = FileCheckpointStore(config.checkpoint_path)
            mission = Mission(
                MissionId("m1"), "resume", scope=("challenge.local",)
            )
            task = Task(
                TaskId("t1"),
                mission.id,
                "resume task",
                required_capabilities=(),
                status=TaskStatus.TOOL_OUTCOME_UNKNOWN,
            )
            await missions.save(mission)
            await tasks.save(task)
            await checkpoints.save("task:t1", {"status": task.status.value})
            await RecoveryService(
                tasks, checkpoints, InProcessEventBus()
            ).resolve(task.id, RecoveryDecision.RETRY)

            result = await resume_ctf(
                config,
                FakeModelProvider([ModelResponse(content="flag{resumed}")]),
                {"XHUNTER_ALLOW_UNSAFE_LOCAL_SANDBOX": "1"},
                "m1",
                r"flag\{[^}\r\n]+\}",
            )
            restored = await FileTaskRepository(config.storage_path).get(task.id)

        self.assertEqual(result.status.value, "completed")
        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.status, TaskStatus.COMPLETED)
