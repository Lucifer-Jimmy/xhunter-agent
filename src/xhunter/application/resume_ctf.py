"""Resume pending work in a persisted CTF Mission."""

from collections.abc import Mapping

from xhunter.application.composition import build_local_runtime
from xhunter.application.config import AppConfig
from xhunter.application.run_ctf import CtfRunResult
from xhunter.contracts.model import ModelProvider
from xhunter.domains.ctf import CtfFlagVerifier
from xhunter.kernel.entities import Task
from xhunter.kernel.types import MissionId
from xhunter.orchestration.planner import RulePlanner
from xhunter.orchestration.scheduler import PriorityScheduler
from xhunter.runtime.skill import SkillCatalog
from xhunter.services import (
    AgentProfile,
    ContextService,
    MissionService,
    ProfileContextProvider,
    Redactor,
)


async def resume_ctf(
    config: AppConfig,
    model: ModelProvider,
    environment: Mapping[str, str],
    mission_id: str,
    flag_pattern: str,
) -> CtfRunResult:
    redactor = Redactor.with_patterns(flag_pattern)
    runtime = build_local_runtime(config, model, environment, redactor)
    identifier = MissionId(mission_id)
    try:
        mission = await runtime.missions.get(identifier)
        if mission is None:
            raise KeyError(f"mission not found: {mission_id}")

        def profile(task: Task) -> AgentProfile:
            return AgentProfile(
                role=(
                    "You are resuming an authorized CTF task. Preserve evidence, "
                    "stay within target scope, and return the flag candidate."
                ),
                required_capabilities=task.required_capabilities,
                max_steps=30,
            )

        service = MissionService(
            runtime.missions,
            runtime.tasks,
            runtime.evidence,
            runtime.checkpoints,
            runtime.events,
            RulePlanner(),
            PriorityScheduler(),
            ProfileContextProvider(
                ContextService(SkillCatalog(), runtime.capabilities), profile
            ),
            runtime.agent,
            CtfFlagVerifier(flag_pattern),
            redactor,
        )
        result = await service.run(identifier)
        persisted = await runtime.missions.get(identifier)
        if persisted is None:
            raise RuntimeError("mission disappeared after resume")
        return CtfRunResult(
            mission_id,
            persisted.status,
            result.completed_tasks,
            result.failed_tasks,
        )
    finally:
        await runtime.close()
