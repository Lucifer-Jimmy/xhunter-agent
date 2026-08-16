"""Local content-addressed artifact storage with atomic writes."""

import asyncio
import hashlib
import json
from pathlib import Path

from xhunter.adapters.atomic import atomic_write
from xhunter.contracts.artifact import ArtifactRef


class LocalArtifactStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    async def put(
        self, content: bytes, metadata: dict[str, str] | None = None
    ) -> ArtifactRef:
        artifact_id = hashlib.sha256(content).hexdigest()
        await asyncio.to_thread(
            self._put,
            artifact_id,
            bytes(content),
            dict(metadata or {}),
        )
        return ArtifactRef(artifact_id, len(content), dict(metadata or {}))

    async def get(self, artifact_id: str) -> bytes:
        _validate_artifact_id(artifact_id)
        try:
            return await asyncio.to_thread(self._content_path(artifact_id).read_bytes)
        except FileNotFoundError as exc:
            raise KeyError(artifact_id) from exc

    def _put(self, artifact_id: str, content: bytes, metadata: dict[str, str]) -> None:
        directory = self._content_path(artifact_id).parent
        directory.mkdir(parents=True, exist_ok=True)
        content_path = self._content_path(artifact_id)
        if not content_path.exists():
            atomic_write(content_path, content)
        metadata_path = content_path.with_suffix(".json")
        if not metadata_path.exists():
            atomic_write(
                metadata_path,
                json.dumps(metadata, ensure_ascii=True, sort_keys=True).encode(),
            )

    def _content_path(self, artifact_id: str) -> Path:
        return self._root / artifact_id[:2] / artifact_id[2:]


def _validate_artifact_id(artifact_id: str) -> None:
    invalid_character = any(
        character not in "0123456789abcdef" for character in artifact_id
    )
    if len(artifact_id) != 64 or invalid_character:
        raise ValueError("artifact id must be a lowercase SHA-256 digest")
