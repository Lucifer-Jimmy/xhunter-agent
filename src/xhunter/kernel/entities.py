"""Core entities. They contain no persistence or infrastructure concerns."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from xhunter.kernel.types import EvidenceId, MissionId, TaskId


def utc_now() -> datetime:
    return datetime.now(UTC)


class MissionStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TOOL_OUTCOME_UNKNOWN = "tool_outcome_unknown"


@dataclass(slots=True)
class Mission:
    id: MissionId
    name: str
    scope: tuple[str, ...] = ()
    status: MissionStatus = MissionStatus.CREATED
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class Task:
    id: TaskId
    mission_id: MissionId
    objective: str
    required_capabilities: tuple[str, ...] = ()
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class Evidence:
    id: EvidenceId
    mission_id: MissionId
    source: str
    content: str
    created_at: datetime = field(default_factory=utc_now)
