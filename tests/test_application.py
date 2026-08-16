import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from xhunter.adapters.memory import FakeModelProvider
from xhunter.application.bootstrap import UnsafeLocalSandboxError
from xhunter.application.cli.main import main
from xhunter.application.composition import build_local_runtime
from xhunter.application.config import load_config


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


class CompositionTests(unittest.TestCase):
    def test_local_runtime_fails_closed_without_override(self) -> None:
        with self.assertRaises(UnsafeLocalSandboxError):
            build_local_runtime(load_config(environment={}), FakeModelProvider([]), {})

    def test_local_runtime_registers_tools_and_disposes_them(self) -> None:
        config = load_config(environment={})
        bundle = build_local_runtime(
            config,
            FakeModelProvider([]),
            {"XHUNTER_ALLOW_UNSAFE_LOCAL_SANDBOX": "1"},
        )
        self.assertIsNotNone(bundle.capabilities.resolve("network.http"))
        bundle.close()
        self.assertIsNone(bundle.capabilities.resolve("network.http"))
