"""Atomic JSON repositories for the local single-process control plane."""

import asyncio
import json
from pathlib import Path

from xhunter.adapters.atomic import atomic_write
from xhunter.adapters.storage.mapper import (
    evidence_to_record,
    mission_from_record,
    mission_to_record,
    task_from_record,
    task_to_record,
)
from xhunter.kernel.entities import Evidence, Mission, Task, TaskStatus
from xhunter.kernel.types import MissionId, TaskId


class _JsonEntityFile:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = asyncio.Lock()

    async def upsert(self, key: str, record: dict[str, object]) -> None:
        async with self._lock:
            records = await asyncio.to_thread(self._read)
            records[key] = record
            await asyncio.to_thread(self._write, records)

    async def get(self, key: str) -> dict[str, object] | None:
        async with self._lock:
            records = await asyncio.to_thread(self._read)
            return records.get(key)

    async def all(self) -> tuple[dict[str, object], ...]:
        async with self._lock:
            records = await asyncio.to_thread(self._read)
            return tuple(records.values())

    def _read(self) -> dict[str, dict[str, object]]:
        try:
            value = json.loads(self._path.read_bytes())
        except FileNotFoundError:
            return {}
        if not isinstance(value, dict) or not all(
            isinstance(key, str) and isinstance(record, dict)
            for key, record in value.items()
        ):
            raise ValueError(f"invalid repository file: {self._path}")
        return value

    def _write(self, records: dict[str, dict[str, object]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(
            self._path,
            json.dumps(records, ensure_ascii=True, sort_keys=True).encode(),
        )


class FileMissionRepository:
    def __init__(self, root: Path) -> None:
        self._file = _JsonEntityFile(root / "missions.json")

    async def save(self, mission: Mission) -> None:
        await self._file.upsert(str(mission.id), mission_to_record(mission))

    async def get(self, mission_id: MissionId) -> Mission | None:
        record = await self._file.get(str(mission_id))
        return None if record is None else mission_from_record(record)


class FileTaskRepository:
    def __init__(self, root: Path) -> None:
        self._file = _JsonEntityFile(root / "tasks.json")

    async def save(self, task: Task) -> None:
        await self._file.upsert(str(task.id), task_to_record(task))

    async def get(self, task_id: TaskId) -> Task | None:
        record = await self._file.get(str(task_id))
        return None if record is None else task_from_record(record)

    async def list_pending(self, mission_id: MissionId) -> list[Task]:
        return [
            task
            for task in await self.list_for_mission(mission_id)
            if task.status == TaskStatus.PENDING
        ]

    async def list_for_mission(self, mission_id: MissionId) -> list[Task]:
        return [
            task_from_record(record)
            for record in await self._file.all()
            if record.get("mission_id") == str(mission_id)
        ]


class FileEvidenceRepository:
    def __init__(self, root: Path) -> None:
        self._file = _JsonEntityFile(root / "evidence.json")

    async def save(self, evidence: Evidence) -> None:
        await self._file.upsert(str(evidence.id), evidence_to_record(evidence))
