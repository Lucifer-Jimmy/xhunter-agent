"""Application command that composes the CTF Domain with the shared runtime."""

from collections.abc import Mapping
from dataclasses import dataclass

from xhunter.application.composition import build_local_runtime
from xhunter.application.config import AppConfig
from xhunter.contracts.model import ModelProvider
from xhunter.domains.ctf import CtfChallenge, CtfDomain, CtfFlagVerifier
from xhunter.kernel.entities import MissionStatus
from xhunter.orchestration.planner import RulePlanner
from xhunter.orchestration.scheduler import PriorityScheduler
from xhunter.runtime.skill import SkillCatalog
from xhunter.services import (
    ContextService,
    MissionService,
    ProfileContextProvider,
    Redactor,
)


@dataclass(frozen=True, slots=True)
class CtfRunResult:
    mission_id: str
    status: MissionStatus
    completed_tasks: int
    failed_tasks: int


async def run_ctf(
    config: AppConfig,
    model: ModelProvider,
    environment: Mapping[str, str],
    challenge: CtfChallenge,
) -> CtfRunResult:
    state = CtfDomain().create_initial_state(challenge)
    runtime = build_local_runtime(config, model, environment)
    try:
        await runtime.missions.save(state.mission)
        await runtime.tasks.save(state.task)
        context = ProfileContextProvider(
            ContextService(SkillCatalog(), runtime.capabilities),
            lambda _task: state.profile,
        )
        service = MissionService(
            runtime.missions,
            runtime.tasks,
            runtime.evidence,
            runtime.checkpoints,
            runtime.events,
            RulePlanner(),
            PriorityScheduler(),
            context,
            runtime.agent,
            CtfFlagVerifier(challenge.flag_pattern),
            Redactor(),
        )
        result = await service.run(state.mission.id)
        return CtfRunResult(
            str(state.mission.id),
            state.mission.status,
            result.completed_tasks,
            result.failed_tasks,
        )
    finally:
        await runtime.close()
