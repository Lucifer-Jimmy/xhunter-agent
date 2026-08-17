import contextlib
import io
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, patch

from xhunter.adapters.memory import FakeModelProvider
from xhunter.application.bootstrap import UnsafeLocalSandboxError
from xhunter.application.cli.main import main
from xhunter.application.composition import build_local_runtime
from xhunter.application.config import load_config, validate_config


class ConfigurationTests(unittest.TestCase):
    def test_loads_toml_and_environment_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "xhunter.toml"
            path.write_text(
                "[sandbox]\nprovider = 'local'\n"
                "[policy]\nallowed_targets = ['challenge.local']\n"
                "[budget]\ntask_tool_calls = 4\n",
                encoding="utf-8",
            )
            config = load_config(
                path,
                {
                    "XHUNTER_ALLOWED_TARGETS": "10.0.0.1, target.local",
                    "XHUNTER_TASK_TOOL_CALLS": "7",
                },
            )
        self.assertEqual(config.allowed_targets, ("10.0.0.1", "target.local"))
        self.assertEqual(config.budget.task_tool_calls, 7)

    def test_cli_doctor_reports_local_mode_as_unsafe(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["doctor"])
        self.assertEqual(exit_code, 0)
        self.assertIn('"local_sandbox_unsafe": true', output.getvalue())

    def test_validation_rejects_unknown_provider_and_invalid_budget(self) -> None:
        with self.assertRaisesRegex(ValueError, "sandbox provider"):
            validate_config(
                replace(load_config(environment={}), sandbox_provider="bad")
            )
        invalid_budget = replace(
            load_config(environment={}).budget,
            task_tool_calls=-1,
        )
        with self.assertRaisesRegex(ValueError, "budget limits"):
            validate_config(
                replace(load_config(environment={}), budget=invalid_budget)
            )

    def test_run_ctf_requires_natural_language_description(self) -> None:
        with self.assertRaises(SystemExit):
            main(
                [
                    "run-ctf",
                    "--name",
                    "challenge",
                    "--category",
                    "web",
                    "--target",
                    "challenge.local",
                ]
            )

    def test_run_ctf_reads_description_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            description = Path(temporary_directory) / "challenge.md"
            description.write_text("分析登录逻辑并寻找 flag。", encoding="utf-8")
            run = AsyncMock()
            run.return_value = type(
                "Result",
                (),
                {
                    "mission_id": "m1",
                    "status": type("Status", (), {"value": "completed"})(),
                    "completed_tasks": 1,
                    "failed_tasks": 0,
                },
            )()
            with patch(
                "xhunter.application.cli.main.build_model_provider",
                return_value=object(),
            ), patch("xhunter.application.cli.main.run_ctf", run):
                with contextlib.redirect_stdout(io.StringIO()):
                    main(
                        [
                            "run-ctf",
                            "--name",
                            "challenge",
                            "--category",
                            "web",
                            "--target",
                            "challenge.local",
                            "--description-file",
                            str(description),
                        ]
                    )
            await_args = run.await_args
            self.assertIsNotNone(await_args)
            assert await_args is not None
            challenge = await_args.args[3]
            self.assertEqual(challenge.description, "分析登录逻辑并寻找 flag。")


class CompositionTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_runtime_fails_closed_without_override(self) -> None:
        with self.assertRaises(UnsafeLocalSandboxError):
            build_local_runtime(load_config(environment={}), FakeModelProvider([]), {})

    async def test_local_runtime_registers_tools_and_disposes_them(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            config = replace(
                load_config(environment={}),
                trace_path=root / "trace.jsonl",
                artifacts_path=root / "artifacts",
                checkpoint_path=root / "checkpoints",
                storage_path=root / "storage",
            )
            bundle = build_local_runtime(
                config,
                FakeModelProvider([]),
                {"XHUNTER_ALLOW_UNSAFE_LOCAL_SANDBOX": "1"},
            )
            self.assertIsNotNone(bundle.capabilities.resolve("network.http"))
            await bundle.close()
            self.assertIsNone(bundle.capabilities.resolve("network.http"))
