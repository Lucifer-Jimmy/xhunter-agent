"""Composition root for the current local runtime."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from xhunter.adapters.memory import (
    InProcessEventBus,
    MemoryArtifactStore,
    MemoryCheckpointStore,
    MemoryEvidenceRepository,
    MemoryMissionRepository,
    MemoryTaskRepository,
)
from xhunter.adapters.tracing import JsonlTracer
from xhunter.application.bootstrap import SandboxConfig, build_mission_sandbox
from xhunter.application.config import AppConfig
from xhunter.application.tool_runtime import build_tool_dispatcher
from xhunter.contracts.event_bus import Event
from xhunter.contracts.model import ModelProvider
from xhunter.contracts.plugin import PluginContext
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
    missions: MemoryMissionRepository
    tasks: MemoryTaskRepository
    evidence: MemoryEvidenceRepository
    checkpoints: MemoryCheckpointStore
    artifacts: MemoryArtifactStore
    events: InProcessEventBus
    disposers: list[Callable[[], None]]

    def close(self) -> None:
        for disposer in reversed(self.disposers):
            disposer()
        self.plugins.stop_all()


def build_local_runtime(
    config: AppConfig,
    model: ModelProvider,
    environment: Mapping[str, str],
) -> RuntimeBundle:
    sandbox = build_mission_sandbox(
        SandboxConfig(config.sandbox_provider), environment
    )
    capabilities = CapabilityRegistry()
    plugins = PluginManager(PluginContext(capabilities.register))
    failure = plugins.start(CoreToolsPlugin(sandbox))
    if failure is not None:
        raise RuntimeError(f"core tools failed: {failure.reason}")

    missions = MemoryMissionRepository()
    tasks = MemoryTaskRepository()
    evidence = MemoryEvidenceRepository()
    checkpoints = MemoryCheckpointStore()
    artifacts = MemoryArtifactStore()
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
    )
