"""ModelProvider decorator for token, cost, and audit controls."""

import asyncio
from dataclasses import dataclass

from xhunter.contracts.event_bus import Event, EventBus
from xhunter.contracts.model import ModelProvider, ModelRequest, ModelResponse, Usage


class ModelBudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ModelBudgetLimits:
    mission_tokens: int
    task_tokens: int
    mission_cost: float
    task_cost: float

    def __post_init__(self) -> None:
        if min(self.mission_tokens, self.task_tokens) < 0:
            raise ValueError("model token limits must not be negative")
        if min(self.mission_cost, self.task_cost) < 0:
            raise ValueError("model cost limits must not be negative")


@dataclass(slots=True)
class _UsageTotal:
    tokens: int = 0
    cost: float = 0.0


class BudgetedModelProvider:
    def __init__(
        self,
        provider: ModelProvider,
        limits: ModelBudgetLimits,
        events: EventBus,
    ) -> None:
        self._provider = provider
        self._limits = limits
        self._events = events
        self._mission_usage: dict[str, _UsageTotal] = {}
        self._task_usage: dict[tuple[str, str], _UsageTotal] = {}
        self._lock = asyncio.Lock()

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if not request.mission_id or not request.task_id:
            raise ModelBudgetExceeded("model budget requires mission_id and task_id")
        await self._assert_available(request)
        await self._events.publish(
            Event(
                "model.called",
                {"mission_id": request.mission_id, "task_id": request.task_id},
            )
        )
        response = await self._provider.generate(request)
        await self._record(request, response.usage)
        await self._events.publish(
            Event(
                "model.completed",
                {
                    "mission_id": request.mission_id,
                    "task_id": request.task_id,
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "cost": response.usage.cost,
                },
            )
        )
        return response

    async def _assert_available(self, request: ModelRequest) -> None:
        async with self._lock:
            mission = self._mission_usage.get(request.mission_id, _UsageTotal())
            task = self._task_usage.get(
                (request.mission_id, request.task_id), _UsageTotal()
            )
            if mission.tokens >= self._limits.mission_tokens:
                raise ModelBudgetExceeded("mission model token budget exhausted")
            if task.tokens >= self._limits.task_tokens:
                raise ModelBudgetExceeded("task model token budget exhausted")
            if mission.cost >= self._limits.mission_cost:
                raise ModelBudgetExceeded("mission model cost budget exhausted")
            if task.cost >= self._limits.task_cost:
                raise ModelBudgetExceeded("task model cost budget exhausted")

    async def _record(self, request: ModelRequest, usage: Usage) -> None:
        async with self._lock:
            mission = self._mission_usage.setdefault(request.mission_id, _UsageTotal())
            task = self._task_usage.setdefault(
                (request.mission_id, request.task_id), _UsageTotal()
            )
            tokens = usage.input_tokens + usage.output_tokens
            mission.tokens += tokens
            mission.cost += usage.cost
            task.tokens += tokens
            task.cost += usage.cost
