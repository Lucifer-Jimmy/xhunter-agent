import tempfile
import unittest
from pathlib import Path

from xhunter.application.architecture import check_architecture


class ArchitectureCheckerTests(unittest.TestCase):
    def test_detects_runtime_to_adapter_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            path = root / "xhunter/runtime/bad.py"
            path.parent.mkdir(parents=True)
            path.write_text(
                "from xhunter.adapters.memory import FakeSandbox\n",
                encoding="utf-8",
            )
            violations = check_architecture(root)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].imported, "xhunter.adapters.memory")

    def test_detects_planner_repository_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            path = root / "xhunter/orchestration/planner/bad.py"
            path.parent.mkdir(parents=True)
            path.write_text(
                "from xhunter.contracts.storage import TaskRepository\n",
                encoding="utf-8",
            )
            violations = check_architecture(root)
        self.assertEqual(len(violations), 1)
        self.assertIn("repositories", violations[0].reason)
