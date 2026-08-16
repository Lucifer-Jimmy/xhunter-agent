"""Single-process Task leases, heartbeats, and expired-work recovery."""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass

from xhunter.contracts.checkpoint import CheckpointStore
from xhunter.contracts.event_bus import Event, EventBus
from xhunter.contracts.storage import TaskRepository
from xhunter.kernel.entities import TaskStatus
from xhunter.kernel.types import TaskId


@dataclass(frozen=True, slots=True)
class TaskLease:
    task_id: TaskId
    owner_id: str
    expires_at: float


class TaskLeaseManager:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._leases: dict[TaskId, TaskLease] = {}
        self._lock = asyncio.Lock()

    async def acquire(
        self, task_id: TaskId, owner_id: str, ttl_seconds: float
    ) -> bool:
        if not owner_id or ttl_seconds <= 0:
            raise ValueError("lease owner must be set and ttl must be positive")
        async with self._lock:
            now = self._clock()
            current = self._leases.get(task_id)
            if current is not None and current.expires_at > now:
                return current.owner_id == owner_id
            self._leases[task_id] = TaskLease(task_id, owner_id, now + ttl_seconds)
            return True

    async def heartbeat(
        self, task_id: TaskId, owner_id: str, ttl_seconds: float
    ) -> bool:
        if ttl_seconds <= 0:
            raise ValueError("lease ttl must be positive")
        async with self._lock:
            current = self._leases.get(task_id)
            now = self._clock()
            if (
                current is None
                or current.owner_id != owner_id
                or current.expires_at <= now
            ):
                return False
            self._leases[task_id] = TaskLease(task_id, owner_id, now + ttl_seconds)
            return True

    async def release(self, task_id: TaskId, owner_id: str) -> bool:
        async with self._lock:
            current = self._leases.get(task_id)
            if current is None or current.owner_id != owner_id:
                return False
            del self._leases[task_id]
            return True

    async def pop_expired(self) -> tuple[TaskLease, ...]:
        async with self._lock:
            now = self._clock()
            expired = tuple(
                lease for lease in self._leases.values() if lease.expires_at <= now
            )
            for lease in expired:
                del self._leases[lease.task_id]
            return expired


class ExpiredTaskRecovery:
    def __init__(
        self,
        leases: TaskLeaseManager,
        tasks: TaskRepository,
        checkpoints: CheckpointStore,
        events: EventBus,
    ) -> None:
        self._leases = leases
        self._tasks = tasks
        self._checkpoints = checkpoints
        self._events = events

    async def recover(self) -> tuple[TaskId, ...]:
        recovered: list[TaskId] = []
        for lease in await self._leases.pop_expired():
            task = await self._tasks.get(lease.task_id)
            if task is None or task.status != TaskStatus.RUNNING:
                continue
            task.status = TaskStatus.TOOL_OUTCOME_UNKNOWN
            await self._tasks.save(task)
            await self._checkpoints.save(
                f"task:{task.id}",
                {
                    "task_id": str(task.id),
                    "status": task.status.value,
                    "reason": "lease expired",
                },
            )
            await self._events.publish(
                Event(
                    "task.recovery_required",
                    {"task_id": str(task.id), "reason": "lease expired"},
                )
            )
            recovered.append(task.id)
        return tuple(recovered)
