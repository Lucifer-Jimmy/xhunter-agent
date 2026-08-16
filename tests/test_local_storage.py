import tempfile
import unittest
from pathlib import Path

from xhunter.adapters.artifacts import LocalArtifactStore
from xhunter.adapters.checkpoint import FileCheckpointStore


class LocalArtifactStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_content_survives_adapter_recreation_and_is_deduplicated(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = LocalArtifactStore(root)
            first_ref = await first.put(b"evidence", {"kind": "tool-output"})
            second_ref = await first.put(b"evidence", {"kind": "tool-output"})
            restored = await LocalArtifactStore(root).get(first_ref.artifact_id)
            files = [path for path in root.rglob("*") if path.is_file()]
        self.assertEqual(first_ref.artifact_id, second_ref.artifact_id)
        self.assertEqual(restored, b"evidence")
        self.assertEqual(len(files), 2)

    async def test_rejects_path_traversal_as_artifact_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = LocalArtifactStore(Path(temporary_directory))
            with self.assertRaises(ValueError):
                await store.get("../secret")


class FileCheckpointStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_state_survives_adapter_recreation_and_delete_is_idempotent(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            await FileCheckpointStore(root).save("task:one/../../", {"step": 3})
            restored = await FileCheckpointStore(root).load("task:one/../../")
            await FileCheckpointStore(root).delete("task:one/../../")
            await FileCheckpointStore(root).delete("task:one/../../")
            missing = await FileCheckpointStore(root).load("task:one/../../")
        self.assertEqual(restored, {"step": 3})
        self.assertIsNone(missing)
