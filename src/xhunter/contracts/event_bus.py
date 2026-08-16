"""In-process event contract."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Event:
    name: str
    payload: object


EventHandler = Callable[[Event], Awaitable[None]]


class EventBus(Protocol):
    async def publish(self, event: Event) -> None:
        ...

    def subscribe(self, name: str, handler: EventHandler) -> Callable[[], None]:
        ...
