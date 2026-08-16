"""First business domain: authorized CTF challenge solving."""

import re
from dataclasses import dataclass
from uuid import uuid4

from xhunter.contracts.agent_executor import AgentExecutionResult
from xhunter.contracts.verification import (
    VerificationContext,
    VerificationResult,
)
from xhunter.kernel.entities import Mission, Task
from xhunter.kernel.types import MissionId, TaskId
from xhunter.services import AgentProfile

CTF_DOMAIN_API_V1 = "1.0"


@dataclass(frozen=True, slots=True)
class CtfChallenge:
    name: str
    category: str
    targets: tuple[str, ...]
    flag_pattern: str = r"(?:flag|ctf)\{[^}\r\n]+\}"

    def validate(self) -> None:
        if not self.name or not self.category:
            raise ValueError("CTF challenge name and category must not be empty")
        if not self.targets:
            raise ValueError("CTF challenge must declare at least one target")
        re.compile(self.flag_pattern)


@dataclass(frozen=True, slots=True)
class CtfInitialState:
    mission: Mission
    task: Task
    profile: AgentProfile


class CtfDomain:
    api_version = CTF_DOMAIN_API_V1

    def create_initial_state(self, challenge: CtfChallenge) -> CtfInitialState:
        challenge.validate()
        mission_id = MissionId(str(uuid4()))
        mission = Mission(mission_id, challenge.name, challenge.targets)
        capabilities = _capabilities(challenge.category)
        task = Task(
            TaskId(str(uuid4())),
            mission_id,
            (
                f"Solve the authorized {challenge.category} CTF challenge: "
                f"{challenge.name}"
            ),
            required_capabilities=capabilities,
            priority=100,
        )
        profile = AgentProfile(
            role=(
                "You are solving an authorized CTF challenge. Preserve evidence, "
                "stay within target scope, and return the flag candidate."
            ),
            required_capabilities=capabilities,
            max_steps=30,
        )
        return CtfInitialState(mission, task, profile)


class CtfFlagVerifier:
    def __init__(self, flag_pattern: str) -> None:
        self._pattern = re.compile(flag_pattern, re.IGNORECASE)

    async def verify(
        self, result: AgentExecutionResult, context: VerificationContext
    ) -> VerificationResult:
        del context
        candidate = self._pattern.search(result.content)
        if candidate is None:
            return VerificationResult(False, "no flag candidate matched the pattern")
        return VerificationResult(True, "flag candidate matched the challenge pattern")


def _capabilities(category: str) -> tuple[str, ...]:
    normalized = category.strip().lower()
    if normalized == "web":
        return (
            "network.http",
            "browser.web",
            "code.python",
            "filesystem.workspace",
        )
    if normalized in {"crypto", "reverse", "pwn", "misc"}:
        return ("system.shell", "code.python", "filesystem.workspace")
    return ("system.shell", "code.python", "filesystem.workspace")
