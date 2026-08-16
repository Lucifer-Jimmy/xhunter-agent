"""Content-addressed artifact storage boundary."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    artifact_id: str
    size: int
    metadata: dict[str, str] = field(default_factory=dict)


class ArtifactStore(Protocol):
    async def put(
        self, content: bytes, metadata: dict[str, str] | None = None
    ) -> ArtifactRef:
        ...

    async def get(self, artifact_id: str) -> bytes:
        ...
