"""Explicit JSON mappers between persistence records and Domain Entities."""

from datetime import datetime

from xhunter.kernel.entities import (
    Evidence,
    Mission,
    MissionStatus,
    Task,
    TaskStatus,
)
from xhunter.kernel.types import EvidenceId, MissionId, TaskId


def mission_to_record(mission: Mission) -> dict[str, object]:
    return {
        "id": str(mission.id),
        "name": mission.name,
        "scope": list(mission.scope),
        "status": mission.status.value,
        "created_at": mission.created_at.isoformat(),
    }


def mission_from_record(record: dict[str, object]) -> Mission:
    return Mission(
        MissionId(_string(record, "id")),
        _string(record, "name"),
        tuple(_string_list(record, "scope")),
        MissionStatus(_string(record, "status")),
        _datetime(record, "created_at"),
    )


def task_to_record(task: Task) -> dict[str, object]:
    return {
        "id": str(task.id),
        "mission_id": str(task.mission_id),
        "objective": task.objective,
        "required_capabilities": list(task.required_capabilities),
        "status": task.status.value,
        "priority": task.priority,
        "created_at": task.created_at.isoformat(),
    }


def task_from_record(record: dict[str, object]) -> Task:
    return Task(
        TaskId(_string(record, "id")),
        MissionId(_string(record, "mission_id")),
        _string(record, "objective"),
        tuple(_string_list(record, "required_capabilities")),
        TaskStatus(_string(record, "status")),
        _integer(record, "priority"),
        _datetime(record, "created_at"),
    )


def evidence_to_record(evidence: Evidence) -> dict[str, object]:
    return {
        "id": str(evidence.id),
        "mission_id": str(evidence.mission_id),
        "source": evidence.source,
        "content": evidence.content,
        "created_at": evidence.created_at.isoformat(),
    }


def evidence_from_record(record: dict[str, object]) -> Evidence:
    return Evidence(
        EvidenceId(_string(record, "id")),
        MissionId(_string(record, "mission_id")),
        _string(record, "source"),
        _string(record, "content"),
        _datetime(record, "created_at"),
    )


def _string(record: dict[str, object], name: str) -> str:
    value = record.get(name)
    if not isinstance(value, str):
        raise ValueError(f"record field must be a string: {name}")
    return value


def _string_list(record: dict[str, object], name: str) -> list[str]:
    value = record.get(name)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"record field must be a string list: {name}")
    return value


def _integer(record: dict[str, object], name: str) -> int:
    value = record.get(name)
    if not isinstance(value, int):
        raise ValueError(f"record field must be an integer: {name}")
    return value


def _datetime(record: dict[str, object], name: str) -> datetime:
    return datetime.fromisoformat(_string(record, name))
