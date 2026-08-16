"""Local-first tracing boundary."""

from typing import Protocol

from xhunter.contracts.event_bus import Event


class Tracer(Protocol):
    async def record(self, event: Event) -> None:
        ...
