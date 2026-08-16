import unittest

from xhunter.adapters.memory import InProcessEventBus, MemoryTaskRepository
from xhunter.contracts.event_bus import Event
from xhunter.contracts.planning import PlanningDecision
from xhunter.kernel.entities import Task
from xhunter.kernel.types import MissionId, TaskId
from xhunter.services import PlanningService


class PlanningServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_validates_deduplicates_persists_and_emits(self) -> None:
        tasks = MemoryTaskRepository()
        existing = Task(
            TaskId("existing"),
            MissionId("m1"),
            "Inspect Target",
            ("network.http",),
        )
        await tasks.save(existing)
        events: list[Event] = []
        bus = InProcessEventBus()

        async def capture(event: Event) -> None:
            events.append(event)

        bus.subscribe("task.created", capture)
        duplicate = Task(
            TaskId("duplicate"),
            MissionId("m1"),
            " inspect target ",
            ("network.http",),
        )
        new = Task(TaskId("new"), MissionId("m1"), "Analyze response")
        result = await PlanningService(tasks, bus).apply(
            MissionId("m1"), PlanningDecision((duplicate, new))
        )

        self.assertEqual(result.created, (new,))
        self.assertEqual(result.duplicate_count, 1)
        self.assertIsNone(await tasks.get(duplicate.id))
        self.assertIs(await tasks.get(new.id), new)
        self.assertEqual([event.name for event in events], ["task.created"])

    async def test_cross_mission_task_is_rejected_before_persistence(self) -> None:
        tasks = MemoryTaskRepository()
        foreign = Task(TaskId("foreign"), MissionId("m2"), "invalid")
        with self.assertRaises(ValueError):
            await PlanningService(tasks, InProcessEventBus()).apply(
                MissionId("m1"), PlanningDecision((foreign,))
            )
        self.assertEqual(await tasks.list_for_mission(MissionId("m1")), [])
