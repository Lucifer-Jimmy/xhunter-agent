"""Atomic per-Mission and per-Task tool-call and wall-clock budgets."""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass

from xhunter.contracts.tool import ToolNext, ToolRequest, ToolResult


@dataclass(frozen=True, slots=True)
class BudgetLimits:
    mission_tool_calls: int
    task_tool_calls: int
    wall_clock_seconds: float

    def __post_init__(self) -> None:
        if self.mission_tool_calls < 0 or self.task_tool_calls < 0:
            raise ValueError("tool-call limits must not be negative")
        if self.wall_clock_seconds <= 0:
            raise ValueError("wall-clock limit must be positive")


@dataclass(slots=True)
class _MissionBudget:
    started_at: float
    tool_calls: int = 0


class BudgetController:
    def __init__(
        self,
        limits: BudgetLimits,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limits = limits
        self._clock = clock
        self._missions: dict[str, _MissionBudget] = {}
        self._tasks: dict[tuple[str, str], int] = {}
        self._lock = asyncio.Lock()

    async def middleware(
        self, request: ToolRequest, call_next: ToolNext
    ) -> ToolResult:
        reason = await self._reserve(request)
        if reason is not None:
            return ToolResult.rejected_result(reason)
        return await call_next(request)

    async def _reserve(self, request: ToolRequest) -> str | None:
        if not request.mission_id or not request.task_id:
            return "budget requires mission_id and task_id"
        async with self._lock:
            now = self._clock()
            mission = self._missions.setdefault(
                request.mission_id, _MissionBudget(started_at=now)
            )
            if now - mission.started_at >= self._limits.wall_clock_seconds:
                return "mission wall-clock budget exhausted"
            if mission.tool_calls >= self._limits.mission_tool_calls:
                return "mission tool-call budget exhausted"

            task_key = (request.mission_id, request.task_id)
            task_calls = self._tasks.get(task_key, 0)
            if task_calls >= self._limits.task_tool_calls:
                return "task tool-call budget exhausted"

            mission.tool_calls += 1
            self._tasks[task_key] = task_calls + 1
            return None

    async def release_mission(self, mission_id: str) -> None:
        async with self._lock:
            self._missions.pop(mission_id, None)
            for key in [key for key in self._tasks if key[0] == mission_id]:
                del self._tasks[key]
