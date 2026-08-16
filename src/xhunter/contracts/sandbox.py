"""Execution boundary. Production implementations must be Docker/OCI based."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SandboxRequest:
    command: tuple[str, ...]
    environment: dict[str, str] = field(default_factory=dict)
    timeout_seconds: float = 30.0
    working_directory: str | None = None
    stdin: bytes | None = None


@dataclass(frozen=True, slots=True)
class SandboxResult:
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


class Sandbox(Protocol):
    async def execute(self, request: SandboxRequest) -> SandboxResult:
        ...
