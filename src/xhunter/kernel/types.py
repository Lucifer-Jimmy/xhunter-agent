"""Small, framework-free value types used by the kernel."""

from typing import NewType

EvidenceId = NewType("EvidenceId", str)
MissionId = NewType("MissionId", str)
TaskId = NewType("TaskId", str)
