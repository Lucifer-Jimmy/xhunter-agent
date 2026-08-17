"""Build bounded Agent requests from inert Skills and registered capabilities."""

from collections.abc import Callable
from dataclasses import dataclass

from xhunter.contracts.agent_executor import AgentExecutionRequest
from xhunter.contracts.model import Message
from xhunter.kernel.entities import Mission, Task
from xhunter.runtime.capability import CapabilityRegistry
from xhunter.runtime.skill import SkillCatalog


@dataclass(frozen=True, slots=True)
class AgentProfile:
    role: str
    skill_ids: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    max_steps: int = 8
    timeout_seconds: float = 900.0


class ContextService:
    def __init__(
        self,
        skills: SkillCatalog,
        capabilities: CapabilityRegistry,
    ) -> None:
        self._skills = skills
        self._capabilities = capabilities

    def build_agent_request(
        self,
        mission_id: str,
        task_id: str,
        profile: AgentProfile,
        messages: tuple[Message, ...] = (),
    ) -> AgentExecutionRequest:
        if not mission_id or not task_id:
            raise ValueError("mission_id and task_id must not be empty")
        if not profile.role.strip():
            raise ValueError("agent role must not be empty")
        skill_prompt = self._skills.render(profile.skill_ids)
        system_prompt = profile.role.strip()
        if skill_prompt:
            system_prompt = f"{system_prompt}\n\n{skill_prompt}"
        return AgentExecutionRequest(
            mission_id=mission_id,
            task_id=task_id,
            system_prompt=system_prompt,
            messages=messages,
            tools=self._capabilities.specs(profile.required_capabilities),
            max_steps=profile.max_steps,
            timeout_seconds=profile.timeout_seconds,
        )


class ProfileContextProvider:
    def __init__(
        self,
        context_service: ContextService,
        resolve_profile: Callable[[Task], AgentProfile],
    ) -> None:
        self._context_service = context_service
        self._resolve_profile = resolve_profile

    def build(
        self,
        mission: Mission,
        task: Task,
        messages: tuple[Message, ...] = (),
    ) -> AgentExecutionRequest:
        mission_message = Message(
            "user",
            (
                f"Task objective: {task.objective}\n"
                f"Authorized targets: {', '.join(mission.scope)}\n"
                "Operate only on these targets. Do not inspect the Host repository, "
                "configuration, credentials, or unrelated local files."
            ),
        )
        return self._context_service.build_agent_request(
            str(mission.id),
            str(task.id),
            self._resolve_profile(task),
            (mission_message, *messages),
        )
