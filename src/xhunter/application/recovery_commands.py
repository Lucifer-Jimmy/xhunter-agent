"""Control-plane-only status and recovery commands."""

from dataclasses import dataclass

from xhunter.adapters.checkpoint import FileCheckpointStore
from xhunter.adapters.storage import FileMissionRepository, FileTaskRepository
from xhunter.adapters.tracing import JsonlTracer
from xhunter.application.config import AppConfig
from xhunter.contracts.event_bus import Event
from xhunter.kernel.entities import MissionStatus, TaskStatus
from xhunter.kernel.types import MissionId, TaskId
from xhunter.services import RecoveryDecision, RecoveryService, Redactor


@dataclass(frozen=True, slots=True)
class TaskStatusView:
    task_id: str
    objective: str
    status: TaskStatus
    checkpoint_present: bool


@dataclass(frozen=True, slots=True)
class MissionStatusView:
    mission_id: str
    name: str
    status: MissionStatus
    tasks: tuple[TaskStatusView, ...]


async def get_mission_status(
    config: AppConfig, mission_id: str
) -> MissionStatusView:
    _require_file_control_plane(config)
    missions = FileMissionRepository(config.storage_path)
    tasks = FileTaskRepository(config.storage_path)
    checkpoints = FileCheckpointStore(config.checkpoint_path)
    mission = await missions.get(MissionId(mission_id))
    if mission is None:
        raise KeyError(f"mission not found: {mission_id}")
    task_views = []
    for task in await tasks.list_for_mission(mission.id):
        checkpoint = await checkpoints.load(f"task:{task.id}")
        task_views.append(
            TaskStatusView(
                str(task.id),
                task.objective,
                task.status,
                checkpoint is not None,
            )
        )
    return MissionStatusView(
        str(mission.id),
        mission.name,
        mission.status,
        tuple(task_views),
    )


async def recover_task(
    config: AppConfig,
    task_id: str,
    decision: RecoveryDecision,
) -> TaskStatusView:
    _require_file_control_plane(config)
    tasks = FileTaskRepository(config.storage_path)
    checkpoints = FileCheckpointStore(config.checkpoint_path)
    tracer = JsonlTracer(config.trace_path, Redactor())

    class TraceEventBus:
        async def publish(self, event: Event) -> None:
            await tracer.record(event)

        def subscribe(self, name, handler):
            del name, handler
            return lambda: None

    service = RecoveryService(tasks, checkpoints, TraceEventBus())
    identifier = TaskId(task_id)
    await service.resolve(identifier, decision)
    task = await tasks.get(identifier)
    if task is None:
        raise RuntimeError("task disappeared after recovery")
    return TaskStatusView(str(task.id), task.objective, task.status, False)


def _require_file_control_plane(config: AppConfig) -> None:
    if config.storage_provider != "file" or config.checkpoint_provider != "file":
        raise ValueError(
            "status and recovery commands require file storage and checkpoints"
        )
