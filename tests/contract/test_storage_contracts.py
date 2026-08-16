import tempfile
from pathlib import Path

import pytest

from xhunter.adapters.artifacts import LocalArtifactStore
from xhunter.adapters.checkpoint import FileCheckpointStore
from xhunter.adapters.memory import MemoryArtifactStore, MemoryCheckpointStore


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["memory", "local"])
async def test_artifact_store_contract(provider: str) -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        store = (
            MemoryArtifactStore()
            if provider == "memory"
            else LocalArtifactStore(Path(temporary_directory))
        )
        first = await store.put(b"same content", {"source": "contract"})
        second = await store.put(b"same content", {"source": "contract"})
        restored = await store.get(first.artifact_id)
    assert first.artifact_id == second.artifact_id
    assert first.size == len(b"same content")
    assert restored == b"same content"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["memory", "file"])
async def test_checkpoint_store_contract(provider: str) -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        store = (
            MemoryCheckpointStore()
            if provider == "memory"
            else FileCheckpointStore(Path(temporary_directory))
        )
        await store.save("task:contract", {"step": 2})
        assert await store.load("task:contract") == {"step": 2}
        await store.delete("task:contract")
        await store.delete("task:contract")
        assert await store.load("task:contract") is None
