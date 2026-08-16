"""In-process event contract."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class Event:
    name: str
    payload: object
    event_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True, slots=True)
class EventDeliveryFailure:
    event_id: str
    event_name: str
    handler_name: str
    reason: str


EventHandler = Callable[[Event], Awaitable[None]]


class EventBus(Protocol):
    async def publish(self, event: Event) -> None:
        ...

    def subscribe(self, name: str, handler: EventHandler) -> Callable[[], None]:
        ...
