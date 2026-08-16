import asyncio
import unittest

from xhunter.adapters.memory import (
    InProcessEventBus,
    MemoryCheckpointStore,
    MemoryTaskRepository,
)
from xhunter.contracts.event_bus import Event
from xhunter.kernel.entities import Task, TaskStatus
from xhunter.kernel.types import MissionId, TaskId
from xhunter.services import ExpiredTaskRecovery, TaskLeaseManager


class EventFailureSemanticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_handler_failures_are_recorded_and_do_not_stop_other_handlers(
        self,
    ) -> None:
        bus = InProcessEventBus()
        delivered: list[str] = []

        async def failing(_event: Event) -> None:
            raise RuntimeError("delivery failed")

        async def healthy(event: Event) -> None:
            delivered.append(event.event_id)

        bus.subscribe("task.completed", failing)
        bus.subscribe("task.completed", healthy)
        event = Event("task.completed", {"task_id": "t1"})
        await bus.publish(event)

        self.assertEqual(delivered, [event.event_id])
        self.assertEqual(bus.failures[0].event_id, event.event_id)
        self.assertEqual(bus.failures[0].reason, "delivery failed")

    def test_each_event_has_an_idempotency_identifier(self) -> None:
        first = Event("test", {})
        second = Event("test", {})
        self.assertTrue(first.event_id)
        self.assertNotEqual(first.event_id, second.event_id)


class TaskLeaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_one_worker_acquires_live_lease(self) -> None:
        leases = TaskLeaseManager(lambda: 10.0)
        results = await asyncio.gather(
            leases.acquire(TaskId("t1"), "worker-a", 30),
            leases.acquire(TaskId("t1"), "worker-b", 30),
        )
        self.assertEqual(sum(results), 1)

    async def test_heartbeat_requires_current_owner_and_unexpired_lease(self) -> None:
        now = 10.0
        leases = TaskLeaseManager(lambda: now)
        await leases.acquire(TaskId("t1"), "worker-a", 5)
        self.assertFalse(await leases.heartbeat(TaskId("t1"), "worker-b", 5))
        now = 16.0
        self.assertFalse(await leases.heartbeat(TaskId("t1"), "worker-a", 5))

    async def test_expired_running_task_becomes_unknown_outcome(self) -> None:
        now = 10.0
        leases = TaskLeaseManager(lambda: now)
        tasks = MemoryTaskRepository()
        task = Task(
            TaskId("t1"),
            MissionId("m1"),
            "running",
            status=TaskStatus.RUNNING,
        )
        await tasks.save(task)
        await leases.acquire(task.id, "worker-a", 5)
        now = 16.0
        checkpoints = MemoryCheckpointStore()
        recovered = await ExpiredTaskRecovery(
            leases, tasks, checkpoints, InProcessEventBus()
        ).recover()
        self.assertEqual(recovered, (task.id,))
        self.assertEqual(task.status, TaskStatus.TOOL_OUTCOME_UNKNOWN)
        self.assertEqual(checkpoints.items["task:t1"]["reason"], "lease expired")
