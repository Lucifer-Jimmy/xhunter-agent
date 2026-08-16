import json
import tempfile
import unittest
from pathlib import Path

from xhunter.adapters.memory import (
    EchoTool,
    FakeSandbox,
    InProcessEventBus,
    MemoryArtifactStore,
    MemoryCheckpointStore,
    MemoryEvidenceRepository,
    MemoryTaskRepository,
)
from xhunter.adapters.tracing import JsonlTracer, NoopTracer
from xhunter.application.tool_runtime import build_tool_dispatcher
from xhunter.contracts.event_bus import Event
from xhunter.contracts.sandbox import SandboxResult
from xhunter.contracts.tool import ToolRequest
from xhunter.kernel.entities import Task, TaskStatus
from xhunter.kernel.types import MissionId, TaskId
from xhunter.orchestration.policies import (
    BudgetController,
    BudgetLimits,
    ScopePolicy,
    ScopePolicyConfig,
)
from xhunter.runtime.capability import CapabilityRegistry
from xhunter.services import RecoveryDecision, RecoveryService, Redactor


class RedactionTests(unittest.TestCase):
    def test_redacts_flags_and_credentials_to_hash_references(self) -> None:
        result = Redactor().redact(
            "found flag{super-secret} token=abcdef123456 password: hunter22"
        )
        self.assertNotIn("super-secret", result.text)
        self.assertNotIn("abcdef123456", result.text)
        self.assertNotIn("hunter22", result.text)
        self.assertEqual(len(result.references), 3)
        self.assertTrue(all(item.startswith("sha256:") for item in result.references))


class JsonlTracerTests(unittest.IsolatedAsyncioTestCase):
    async def test_writes_append_only_redacted_json_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "trace.jsonl"
            tracer = JsonlTracer(path, Redactor())
            await tracer.record(Event("tool.completed", {"output": "flag{hidden}"}))
            await tracer.record(Event("task.completed", {"task_id": "t1"}))
            lines = path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), 2)
        self.assertNotIn("flag{hidden}", lines[0])
        self.assertEqual(json.loads(lines[0])["name"], "tool.completed")
        await NoopTracer().record(Event("ignored", {}))


class EvidenceCaptureTests(unittest.IsolatedAsyncioTestCase):
    async def test_redacts_result_and_persists_evidence(self) -> None:
        registry = CapabilityRegistry()
        registry.register(
            EchoTool(FakeSandbox(SandboxResult(0, stdout="flag{secret}")))
        )
        evidence = MemoryEvidenceRepository()
        artifacts = MemoryArtifactStore()
        dispatcher = build_tool_dispatcher(
            registry,
            BudgetController(BudgetLimits(10, 10, 60)),
            ScopePolicy(ScopePolicyConfig(())),
            InProcessEventBus(),
            evidence,
            artifacts,
            Redactor(),
        )
        result = await dispatcher.dispatch(
            ToolRequest("test.echo", mission_id="m1", task_id="t1")
        )
        persisted = next(iter(evidence.items.values()))
        self.assertNotIn("flag{secret}", result.output)
        self.assertEqual(result.output, persisted.content)

    async def test_spills_large_redacted_output_to_artifact(self) -> None:
        registry = CapabilityRegistry()
        registry.register(EchoTool(FakeSandbox(SandboxResult(0, stdout="x" * 20_000))))
        evidence = MemoryEvidenceRepository()
        artifacts = MemoryArtifactStore()
        dispatcher = build_tool_dispatcher(
            registry,
            BudgetController(BudgetLimits(10, 10, 60)),
            ScopePolicy(ScopePolicyConfig(())),
            InProcessEventBus(),
            evidence,
            artifacts,
        )
        await dispatcher.dispatch(
            ToolRequest("test.echo", mission_id="m1", task_id="t1")
        )
        persisted = next(iter(evidence.items.values()))
        self.assertTrue(persisted.content.startswith("artifact:"))
        self.assertEqual(len(artifacts.items), 1)


class RecoveryServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_retry_returns_unknown_task_to_pending_and_clears_checkpoint(
        self,
    ) -> None:
        tasks = MemoryTaskRepository()
        task = Task(
            TaskId("t1"),
            MissionId("m1"),
            "recover",
            status=TaskStatus.TOOL_OUTCOME_UNKNOWN,
        )
        await tasks.save(task)
        checkpoints = MemoryCheckpointStore()
        await checkpoints.save("task:t1", {"status": "tool_outcome_unknown"})
        await RecoveryService(tasks, checkpoints, InProcessEventBus()).resolve(
            task.id, RecoveryDecision.RETRY
        )
        self.assertEqual(task.status, TaskStatus.PENDING)
        self.assertNotIn("task:t1", checkpoints.items)

    async def test_non_unknown_task_cannot_be_recovered(self) -> None:
        tasks = MemoryTaskRepository()
        task = Task(TaskId("t1"), MissionId("m1"), "pending")
        await tasks.save(task)
        with self.assertRaises(ValueError):
            await RecoveryService(
                tasks, MemoryCheckpointStore(), InProcessEventBus()
            ).resolve(task.id, RecoveryDecision.FAIL)
