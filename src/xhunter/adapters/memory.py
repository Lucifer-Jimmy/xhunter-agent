"""Dependency-free adapters used by W1 tests and local development."""

import hashlib
from collections import defaultdict

from xhunter.contracts.artifact import ArtifactRef, ArtifactStore
from xhunter.contracts.checkpoint import CheckpointStore
from xhunter.contracts.event_bus import Event, EventHandler
from xhunter.contracts.model import ModelProvider, ModelRequest, ModelResponse
from xhunter.contracts.policy import PolicyDecision
from xhunter.contracts.sandbox import Sandbox, SandboxRequest, SandboxResult
from xhunter.contracts.storage import (
    EvidenceRepository,
    MissionRepository,
    TaskRepository,
)
from xhunter.contracts.tool import ToolRequest, ToolResult, ToolSpec
from xhunter.kernel.entities import Evidence, Mission, Task, TaskStatus
from xhunter.kernel.types import MissionId, TaskId


class MemoryMissionRepository(MissionRepository):
    def __init__(self) -> None:
        self.items: dict[MissionId, Mission] = {}

    async def save(self, mission: Mission) -> None:
        self.items[mission.id] = mission

    async def get(self, mission_id: MissionId) -> Mission | None:
        return self.items.get(mission_id)


class MemoryTaskRepository(TaskRepository):
    def __init__(self) -> None:
        self.items: dict[TaskId, Task] = {}

    async def save(self, task: Task) -> None:
        self.items[task.id] = task

    async def get(self, task_id: TaskId) -> Task | None:
        return self.items.get(task_id)

    async def list_pending(self, mission_id: MissionId) -> list[Task]:
        return [
            task
            for task in self.items.values()
            if task.mission_id == mission_id and task.status == TaskStatus.PENDING
        ]


class MemoryEvidenceRepository(EvidenceRepository):
    def __init__(self) -> None:
        self.items: dict[str, Evidence] = {}

    async def save(self, evidence: Evidence) -> None:
        self.items[str(evidence.id)] = evidence


class MemoryCheckpointStore(CheckpointStore):
    def __init__(self) -> None:
        self.items: dict[str, dict[str, object]] = {}

    async def save(self, key: str, state: dict[str, object]) -> None:
        self.items[key] = dict(state)

    async def load(self, key: str) -> dict[str, object] | None:
        state = self.items.get(key)
        return None if state is None else dict(state)

    async def delete(self, key: str) -> None:
        self.items.pop(key, None)


class MemoryArtifactStore(ArtifactStore):
    def __init__(self) -> None:
        self.items: dict[str, bytes] = {}

    async def put(
        self, content: bytes, metadata: dict[str, str] | None = None
    ) -> ArtifactRef:
        artifact_id = hashlib.sha256(content).hexdigest()
        self.items[artifact_id] = bytes(content)
        return ArtifactRef(artifact_id, len(content), dict(metadata or {}))

    async def get(self, artifact_id: str) -> bytes:
        return self.items[artifact_id]


class InProcessEventBus:
    def __init__(self) -> None:
        self.handlers: dict[str, list[EventHandler]] = defaultdict(list)

    async def publish(self, event: Event) -> None:
        for handler in tuple(self.handlers.get(event.name, ())):
            try:
                await handler(event)
            except Exception:
                continue

    def subscribe(self, name: str, handler: EventHandler):
        self.handlers[name].append(handler)

        def dispose() -> None:
            if handler in self.handlers[name]:
                self.handlers[name].remove(handler)

        return dispose


class AllowAllPolicy:
    async def authorize(self, request: ToolRequest) -> PolicyDecision:
        return PolicyDecision(allowed=True)


class FakeSandbox(Sandbox):
    def __init__(self, result: SandboxResult | None = None) -> None:
        self.requests: list[SandboxRequest] = []
        self.result = result or SandboxResult(exit_code=0)

    async def execute(self, request: SandboxRequest) -> SandboxResult:
        self.requests.append(request)
        return self.result


class EchoTool:
    capability = "test.echo"
    spec = ToolSpec(
        capability=capability,
        description="Echo a value through the configured sandbox.",
        input_schema={
            "type": "object",
            "properties": {"value": {"type": "string"}},
        },
    )

    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox

    async def execute(self, request: ToolRequest) -> ToolResult:
        value = str(request.arguments.get("value", ""))
        result = await self._sandbox.execute(SandboxRequest(("echo", value)))
        return ToolResult(
            ok=result.exit_code == 0,
            output=result.stdout,
            error=result.stderr or None,
        )


class FakeModelProvider(ModelProvider):
    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[ModelRequest] = []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if not self.responses:
            raise RuntimeError("FakeModelProvider has no response left")
        return self.responses.pop(0)
