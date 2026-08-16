"""Composition root for the current local runtime."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from xhunter.adapters.artifacts import LocalArtifactStore
from xhunter.adapters.checkpoint import FileCheckpointStore
from xhunter.adapters.memory import (
    InProcessEventBus,
    MemoryArtifactStore,
    MemoryCheckpointStore,
    MemoryEvidenceRepository,
    MemoryMissionRepository,
    MemoryTaskRepository,
)
from xhunter.adapters.storage import (
    FileEvidenceRepository,
    FileMissionRepository,
    FileTaskRepository,
)
from xhunter.adapters.tracing import JsonlTracer
from xhunter.application.bootstrap import SandboxConfig, build_mission_sandbox
from xhunter.application.config import AppConfig
from xhunter.application.tool_runtime import build_tool_dispatcher
from xhunter.contracts.artifact import ArtifactStore
from xhunter.contracts.checkpoint import CheckpointStore
from xhunter.contracts.event_bus import Event
from xhunter.contracts.model import ModelProvider
from xhunter.contracts.plugin import PluginContext
from xhunter.contracts.sandbox import Sandbox
from xhunter.contracts.storage import (
    EvidenceRepository,
    MissionRepository,
    TaskRepository,
)
from xhunter.orchestration.policies import (
    BudgetController,
    BudgetLimits,
    ScopePolicy,
    ScopePolicyConfig,
)
from xhunter.plugins.builtin import CoreToolsPlugin
from xhunter.runtime.agent import (
    BudgetedModelProvider,
    ModelBudgetLimits,
    ReActAgentExecutor,
)
from xhunter.runtime.capability import CapabilityRegistry
from xhunter.runtime.plugin import PluginManager
from xhunter.services.redaction import Redactor


@dataclass(slots=True)
class RuntimeBundle:
    agent: ReActAgentExecutor
    capabilities: CapabilityRegistry
    plugins: PluginManager
    missions: MissionRepository
    tasks: TaskRepository
    evidence: EvidenceRepository
    checkpoints: CheckpointStore
    artifacts: ArtifactStore
    events: InProcessEventBus
    disposers: list[Callable[[], None]]
    sandbox: Sandbox

    async def close(self) -> None:
        for disposer in reversed(self.disposers):
            disposer()
        self.plugins.stop_all()
        await self.sandbox.close()


def build_local_runtime(
    config: AppConfig,
    model: ModelProvider,
    environment: Mapping[str, str],
) -> RuntimeBundle:
    sandbox = build_mission_sandbox(
        SandboxConfig(
            provider=config.sandbox_provider,
            image=config.sandbox_image,
            runtime=config.sandbox_runtime,
            docker_host=config.docker_host,
            network_name=config.sandbox_network,
            workspace=config.sandbox_workspace,
        ),
        environment,
    )
    capabilities = CapabilityRegistry()
    plugins = PluginManager(PluginContext(capabilities.register))
    failure = plugins.start(CoreToolsPlugin(sandbox))
    if failure is not None:
        raise RuntimeError(f"core tools failed: {failure.reason}")

    missions, tasks, evidence = _build_repositories(config)
    checkpoints = _build_checkpoints(config)
    artifacts = _build_artifacts(config)
    events = InProcessEventBus()
    redactor = Redactor()
    tracer = JsonlTracer(config.trace_path, redactor)

    async def trace(event: Event) -> None:
        await tracer.record(event)

    disposers = [
        events.subscribe(event_name, trace)
        for event_name in (
            "tool.called",
            "tool.completed",
            "evidence.created",
            "task.completed",
            "task.failed",
            "model.called",
            "model.completed",
            "model.failed",
        )
    ]

    budget = BudgetController(
        BudgetLimits(
            config.budget.mission_tool_calls,
            config.budget.task_tool_calls,
            config.budget.wall_clock_seconds,
        )
    )
    policy = ScopePolicy(
        ScopePolicyConfig(config.allowed_targets, config.blocked_targets)
    )
    dispatcher = build_tool_dispatcher(
        capabilities,
        budget,
        policy,
        events,
        evidence,
        artifacts,
        redactor,
    )
    budgeted_model = BudgetedModelProvider(
        model,
        ModelBudgetLimits(
            config.budget.mission_model_tokens,
            config.budget.task_model_tokens,
            config.budget.mission_model_cost,
            config.budget.task_model_cost,
        ),
        events,
    )
    return RuntimeBundle(
        ReActAgentExecutor(budgeted_model, dispatcher),
        capabilities,
        plugins,
        missions,
        tasks,
        evidence,
        checkpoints,
        artifacts,
        events,
        disposers,
        sandbox,
    )


def _build_artifacts(config: AppConfig) -> ArtifactStore:
    if config.artifacts_provider == "local":
        return LocalArtifactStore(config.artifacts_path)
    if config.artifacts_provider == "memory":
        return MemoryArtifactStore()
    raise ValueError(f"unsupported artifacts provider: {config.artifacts_provider}")


def _build_checkpoints(config: AppConfig) -> CheckpointStore:
    if config.checkpoint_provider == "file":
        return FileCheckpointStore(config.checkpoint_path)
    if config.checkpoint_provider == "memory":
        return MemoryCheckpointStore()
    raise ValueError(f"unsupported checkpoint provider: {config.checkpoint_provider}")


def _build_repositories(
    config: AppConfig,
) -> tuple[MissionRepository, TaskRepository, EvidenceRepository]:
    if config.storage_provider == "file":
        return (
            FileMissionRepository(config.storage_path),
            FileTaskRepository(config.storage_path),
            FileEvidenceRepository(config.storage_path),
        )
    if config.storage_provider == "memory":
        return (
            MemoryMissionRepository(),
            MemoryTaskRepository(),
            MemoryEvidenceRepository(),
        )
    raise ValueError(f"unsupported storage provider: {config.storage_provider}")
