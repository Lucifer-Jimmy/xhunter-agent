"""Build bounded Agent requests from inert Skills and registered capabilities."""

from dataclasses import dataclass

from xhunter.contracts.agent_executor import AgentExecutionRequest
from xhunter.contracts.model import Message
from xhunter.runtime.capability import CapabilityRegistry
from xhunter.runtime.skill import SkillCatalog


@dataclass(frozen=True, slots=True)
class AgentProfile:
    role: str
    skill_ids: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    max_steps: int = 8


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
        )
