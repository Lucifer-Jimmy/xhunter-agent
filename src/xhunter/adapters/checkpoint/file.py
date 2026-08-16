"""Atomic JSON file checkpoints for local crash recovery."""

import asyncio
import hashlib
import json
from pathlib import Path

from xhunter.adapters.atomic import atomic_write


class FileCheckpointStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    async def save(self, key: str, state: dict[str, object]) -> None:
        if not key:
            raise ValueError("checkpoint key must not be empty")
        content = json.dumps(state, ensure_ascii=True, sort_keys=True).encode()
        path = self._path(key)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(atomic_write, path, content)

    async def load(self, key: str) -> dict[str, object] | None:
        if not key:
            raise ValueError("checkpoint key must not be empty")
        try:
            content = await asyncio.to_thread(self._path(key).read_bytes)
        except FileNotFoundError:
            return None
        value = json.loads(content)
        if not isinstance(value, dict):
            raise ValueError("checkpoint root must be an object")
        return value

    async def delete(self, key: str) -> None:
        if not key:
            raise ValueError("checkpoint key must not be empty")
        try:
            await asyncio.to_thread(self._path(key).unlink)
        except FileNotFoundError:
            pass

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()
        return self._root / digest[:2] / f"{digest[2:]}.json"
