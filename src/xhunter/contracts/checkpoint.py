"""Crash-recovery checkpoint boundary."""

from typing import Protocol


class CheckpointStore(Protocol):
    async def save(self, key: str, state: dict[str, object]) -> None:
        ...

    async def load(self, key: str) -> dict[str, object] | None:
        ...

    async def delete(self, key: str) -> None:
        ...
