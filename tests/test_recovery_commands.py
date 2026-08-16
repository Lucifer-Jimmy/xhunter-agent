import asyncio
import contextlib
import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from xhunter.adapters.checkpoint import FileCheckpointStore
from xhunter.adapters.storage import FileMissionRepository, FileTaskRepository
from xhunter.application.cli.main import main
from xhunter.application.config import load_config
from xhunter.application.recovery_commands import (
    get_mission_status,
    recover_task,
)
from xhunter.kernel.entities import Mission, Task, TaskStatus
from xhunter.kernel.types import MissionId, TaskId
from xhunter.services import RecoveryDecision


class RecoveryCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_status_and_retry_use_persisted_control_plane_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            config = replace(
                load_config(environment={}),
                storage_path=root / "storage",
                checkpoint_path=root / "checkpoints",
                trace_path=root / "trace.jsonl",
            )
            mission = Mission(MissionId("m1"), "challenge")
            task = Task(
                TaskId("t1"),
                mission.id,
                "recover",
                status=TaskStatus.TOOL_OUTCOME_UNKNOWN,
            )
            await FileMissionRepository(config.storage_path).save(mission)
            await FileTaskRepository(config.storage_path).save(task)
            await FileCheckpointStore(config.checkpoint_path).save(
                "task:t1", {"status": task.status.value}
            )

            status = await get_mission_status(config, "m1")
            recovered = await recover_task(config, "t1", RecoveryDecision.RETRY)
            checkpoint = await FileCheckpointStore(config.checkpoint_path).load(
                "task:t1"
            )

        self.assertEqual(status.tasks[0].status, TaskStatus.TOOL_OUTCOME_UNKNOWN)
        self.assertTrue(status.tasks[0].checkpoint_present)
        self.assertEqual(recovered.status, TaskStatus.PENDING)
        self.assertIsNone(checkpoint)

    async def test_memory_control_plane_is_rejected(self) -> None:
        config = replace(
            load_config(environment={}),
            storage_provider="memory",
            checkpoint_provider="memory",
        )
        with self.assertRaises(ValueError):
            await get_mission_status(config, "m1")


class RecoveryCliTests(unittest.TestCase):
    def test_status_cli_outputs_structured_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            config_path = root / "xhunter.toml"
            storage_path = root / "storage"
            checkpoint_path = root / "checkpoints"
            config_path.write_text(
                f"[storage]\nprovider='file'\npath='{storage_path}'\n"
                f"[checkpoint]\nprovider='file'\npath='{checkpoint_path}'\n",
                encoding="utf-8",
            )
            asyncio.run(
                FileMissionRepository(storage_path).save(
                    Mission(MissionId("m1"), "persisted")
                )
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = main(
                    ["--config", str(config_path), "status", "--mission-id", "m1"]
                )
            payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "created")
