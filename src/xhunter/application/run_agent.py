"""Application command for one bounded Agent execution."""

from collections.abc import Mapping
from pathlib import Path

from xhunter.application.composition import build_local_runtime
from xhunter.application.config import AppConfig
from xhunter.contracts.model import Message, ModelProvider
from xhunter.runtime.skill import SkillCatalog, load_skill_directory
from xhunter.services import AgentProfile, ContextService


async def run_agent(
    config: AppConfig,
    model: ModelProvider,
    environment: Mapping[str, str],
    prompt: str,
    capabilities: tuple[str, ...],
    skill_directories: tuple[Path, ...] = (),
    mission_id: str = "local-mission",
    task_id: str = "local-task",
) -> str:
    if not prompt.strip():
        raise ValueError("prompt must not be empty")
    runtime = build_local_runtime(config, model, environment)
    skills = SkillCatalog()
    skill_ids: list[str] = []
    skill_disposers = []
    try:
        for directory in skill_directories:
            skill = load_skill_directory(directory)
            skill_ids.append(skill.skill_id)
            skill_disposers.append(skills.register(skill))
        request = ContextService(skills, runtime.capabilities).build_agent_request(
            mission_id,
            task_id,
            AgentProfile(
                role="You are an authorized security research agent.",
                skill_ids=tuple(skill_ids),
                required_capabilities=capabilities,
            ),
            (Message("user", prompt),),
        )
        result = await runtime.agent.execute(request)
        return result.content
    finally:
        for dispose in reversed(skill_disposers):
            dispose()
        await runtime.close()
