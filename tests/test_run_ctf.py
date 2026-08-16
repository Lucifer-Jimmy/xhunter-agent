import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from xhunter.adapters.memory import FakeModelProvider
from xhunter.application.config import load_config
from xhunter.application.run_ctf import run_ctf
from xhunter.contracts.model import ModelResponse
from xhunter.domains.ctf import CtfChallenge
from xhunter.kernel.entities import MissionStatus


class RunCtfTests(unittest.IsolatedAsyncioTestCase):
    async def test_runs_ctf_mission_end_to_end_with_shared_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            config = replace(
                load_config(environment={}),
                allowed_targets=("challenge.local",),
                trace_path=root / "trace.jsonl",
                artifacts_path=root / "artifacts",
                checkpoint_path=root / "checkpoints",
            )
            result = await run_ctf(
                config,
                FakeModelProvider([ModelResponse(content="flag{completed}")]),
                {"XHUNTER_ALLOW_UNSAFE_LOCAL_SANDBOX": "1"},
                CtfChallenge(
                    "Local Web",
                    "web",
                    ("challenge.local",),
                    r"flag\{[a-z]+\}",
                ),
            )
            trace = (root / "trace.jsonl").read_text(encoding="utf-8")

        self.assertEqual(result.status, MissionStatus.COMPLETED)
        self.assertEqual(result.completed_tasks, 1)
        self.assertNotIn("flag{completed}", trace)

    async def test_missing_flag_fails_ctf_mission(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            config = replace(
                load_config(environment={}),
                trace_path=root / "trace.jsonl",
                artifacts_path=root / "artifacts",
                checkpoint_path=root / "checkpoints",
            )
            result = await run_ctf(
                config,
                FakeModelProvider([ModelResponse(content="no candidate")]),
                {"XHUNTER_ALLOW_UNSAFE_LOCAL_SANDBOX": "1"},
                CtfChallenge("Local Misc", "misc", ("local",)),
            )
        self.assertEqual(result.status, MissionStatus.FAILED)
        self.assertEqual(result.failed_tasks, 1)
