import importlib
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from xhunter.adapters.memory import FakeModelProvider
from xhunter.application.config import load_config
from xhunter.application.run_agent import run_agent
from xhunter.contracts.model import ModelResponse


class LocalAgentCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_agent_injects_skill_and_returns_model_answer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            config = replace(
                load_config(environment={}),
                trace_path=root / "trace.jsonl",
                artifacts_path=root / "artifacts",
                checkpoint_path=root / "checkpoints",
                storage_path=root / "storage",
            )
            result = await run_agent(
                config,
                FakeModelProvider([ModelResponse(content="answer")]),
                {"XHUNTER_ALLOW_UNSAFE_LOCAL_SANDBOX": "1"},
                "inspect the target",
                (),
                (Path("examples/skills/ctf-web-enumeration"),),
            )
        self.assertEqual(result, "answer")

    async def test_run_agent_requires_explicit_local_override(self) -> None:
        with self.assertRaises(RuntimeError):
            await run_agent(
                load_config(environment={}),
                FakeModelProvider([]),
                {},
                "inspect the target",
                (),
            )


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_public_packages_import(self) -> None:
        for package in (
            "xhunter.kernel",
            "xhunter.contracts",
            "xhunter.runtime",
            "xhunter.orchestration",
            "xhunter.services",
        ):
            self.assertIsNotNone(importlib.import_module(package))

    def test_kernel_and_contracts_have_no_forbidden_framework_imports(self) -> None:
        forbidden = {
            "langgraph",
            "langchain",
            "openai",
            "anthropic",
            "playwright",
            "docker",
            "sqlalchemy",
            "fastapi",
            "httpx",
            "deepseek",
        }
        for path in Path("src/xhunter/kernel").glob("*.py"):
            self._assert_no_import(path, forbidden)
        for path in Path("src/xhunter/contracts").glob("*.py"):
            self._assert_no_import(path, forbidden)

    def test_tool_layers_do_not_import_host_execution_libraries(self) -> None:
        forbidden = {
            "subprocess",
            "httpx",
            "socket",
            "requests",
            "playwright",
            "docker",
        }
        for root in (Path("src/xhunter/plugins"), Path("src/xhunter/runtime")):
            for path in root.rglob("*.py"):
                self._assert_no_import(path, forbidden)

    def _assert_no_import(self, path: Path, forbidden: set[str]) -> None:
        source = path.read_text(encoding="utf-8")
        for name in forbidden:
            self.assertNotRegex(source, rf"(?m)^\s*(?:from|import)\s+{name}(?:\.|\s|$)")
