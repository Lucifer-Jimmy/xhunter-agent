import asyncio
import unittest

from xhunter.adapters.memory import (
    MemoryCheckpointStore,
    MemoryEvidenceRepository,
    MemoryMissionRepository,
    MemoryTaskRepository,
)
from xhunter.contracts.agent_executor import (
    AgentExecutionRequest,
    AgentExecutionResult,
)
from xhunter.contracts.event_bus import Event, EventHandler
from xhunter.contracts.planning import PlanningDecision
from xhunter.contracts.verification import VerificationResult
from xhunter.kernel.entities import Mission, MissionStatus, Task, TaskStatus
from xhunter.kernel.types import MissionId, TaskId
from xhunter.orchestration.scheduler import PriorityScheduler
from xhunter.services import MissionService


class RecordingEventBus:
    def __init__(self) -> None:
        self.events: list[Event] = []

    async def publish(self, event: Event) -> None:
        self.events.append(event)

    def subscribe(self, name: str, handler: EventHandler):
        del name, handler
        return lambda: None


class StaticPlanner:
    def __init__(self, tasks=()) -> None:
        self.tasks = tasks

    async def plan(self, _context):
        tasks, self.tasks = self.tasks, ()
        return PlanningDecision(tasks=tasks)


class StaticContextProvider:
    def build(self, mission, task, messages=()):
        return AgentExecutionRequest(
            mission_id=str(mission.id),
            task_id=str(task.id),
            messages=messages,
        )


class StaticAgent:
    def __init__(self, result: AgentExecutionResult) -> None:
        self.result = result
        self.requests: list[AgentExecutionRequest] = []

    async def execute(self, request):
        self.requests.append(request)
        return self.result


class FailingAgent:
    async def execute(self, _request):
        raise RuntimeError("worker disconnected")


class SensitiveFailingAgent:
    async def execute(self, _request):
        raise RuntimeError("flag{checkpoint_secret}")


class BlockingAgent:
    async def execute(self, _request):
        await asyncio.sleep(60)
        return AgentExecutionResult("unexpected", 1)


class StaticVerifier:
    def __init__(self, accepted: bool) -> None:
        self.accepted = accepted

    async def verify(self, _result, _context):
        return VerificationResult(self.accepted, "verification decision")


class MissionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.missions = MemoryMissionRepository()
        self.tasks = MemoryTaskRepository()
        self.evidence = MemoryEvidenceRepository()
        self.checkpoints = MemoryCheckpointStore()
        self.events = RecordingEventBus()
        self.mission = Mission(MissionId("m1"), "challenge")
        await self.missions.save(self.mission)

    def service(self, planner, agent, verifier) -> MissionService:
        return MissionService(
            self.missions,
            self.tasks,
            self.evidence,
            self.checkpoints,
            self.events,
            planner,
            PriorityScheduler(),
            StaticContextProvider(),
            agent,
            verifier,
        )

    async def test_runs_planned_task_and_persists_evidence(self) -> None:
        low = Task(TaskId("low"), self.mission.id, "low", priority=1)
        high = Task(TaskId("high"), self.mission.id, "high", priority=10)
        agent = StaticAgent(AgentExecutionResult("analysis complete", 1))
        result = await self.service(
            StaticPlanner((low, high)), agent, StaticVerifier(True)
        ).run(self.mission.id)

        self.assertEqual(result.completed_tasks, 2)
        saved_high = await self.tasks.get(high.id)
        self.assertIsNotNone(saved_high)
        assert saved_high is not None
        self.assertEqual(saved_high.status, TaskStatus.COMPLETED)
        self.assertEqual(agent.requests[0].task_id, "high")
        self.assertEqual(len(self.evidence.items), 2)
        self.assertEqual(self.mission.status, MissionStatus.COMPLETED)
        self.assertEqual(self.checkpoints.items, {})

    async def test_verifier_rejection_fails_task_and_mission(self) -> None:
        task = Task(TaskId("t1"), self.mission.id, "test")
        result = await self.service(
            StaticPlanner((task,)),
            StaticAgent(AgentExecutionResult("candidate", 1)),
            StaticVerifier(False),
        ).run(self.mission.id)
        self.assertEqual(result.failed_tasks, 1)
        self.assertEqual(task.status, TaskStatus.FAILED)
        self.assertEqual(self.mission.status, MissionStatus.FAILED)

    async def test_agent_crash_marks_unknown_and_preserves_checkpoint(self) -> None:
        task = Task(TaskId("t1"), self.mission.id, "test")
        result = await self.service(
            StaticPlanner((task,)), FailingAgent(), StaticVerifier(True)
        ).run(self.mission.id)
        self.assertEqual(result.failed_tasks, 1)
        self.assertEqual(task.status, TaskStatus.TOOL_OUTCOME_UNKNOWN)
        self.assertEqual(
            self.checkpoints.items["task:t1"]["status"],
            TaskStatus.TOOL_OUTCOME_UNKNOWN.value,
        )
        self.assertIn(
            "task.recovery_required", [event.name for event in self.events.events]
        )

    async def test_checkpoint_records_exception_type_without_sensitive_detail(
        self,
    ) -> None:
        task = Task(TaskId("t1"), self.mission.id, "test")
        await self.service(
            StaticPlanner((task,)), SensitiveFailingAgent(), StaticVerifier(True)
        ).run(self.mission.id)
        checkpoint = self.checkpoints.items["task:t1"]
        self.assertEqual(checkpoint["error_type"], "RuntimeError")
        self.assertNotIn("checkpoint_secret", repr(checkpoint))

    async def test_rejects_planner_task_for_another_mission(self) -> None:
        foreign = Task(TaskId("foreign"), MissionId("m2"), "invalid")
        with self.assertRaises(ValueError):
            await self.service(
                StaticPlanner((foreign,)),
                StaticAgent(AgentExecutionResult("unused", 1)),
                StaticVerifier(True),
            ).run(self.mission.id)
        self.assertIsNone(await self.tasks.get(foreign.id))

    async def test_task_limit_leaves_mission_running_when_work_remains(self) -> None:
        first = Task(TaskId("first"), self.mission.id, "first", priority=2)
        second = Task(TaskId("second"), self.mission.id, "second", priority=1)
        result = await self.service(
            StaticPlanner((first, second)),
            StaticAgent(AgentExecutionResult("complete", 1)),
            StaticVerifier(True),
        ).run(self.mission.id, max_tasks=1)
        self.assertEqual(result.completed_tasks, 1)
        self.assertEqual(self.mission.status, MissionStatus.RUNNING)
        self.assertEqual(second.status, TaskStatus.PENDING)

    async def test_external_cancellation_marks_task_unknown_and_rethrows(self) -> None:
        task = Task(TaskId("t1"), self.mission.id, "blocking")
        operation = asyncio.create_task(
            self.service(
                StaticPlanner((task,)), BlockingAgent(), StaticVerifier(True)
            ).run(self.mission.id)
        )
        while task.status != TaskStatus.RUNNING:
            await asyncio.sleep(0)
        operation.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await operation
        self.assertEqual(task.status, TaskStatus.TOOL_OUTCOME_UNKNOWN)
        self.assertEqual(
            self.checkpoints.items["task:t1"]["error_type"], "CancelledError"
        )
