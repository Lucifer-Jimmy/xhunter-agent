"""Long-lived Docker/OCI sandbox using an internal network by default."""

import asyncio
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from xhunter.contracts.sandbox import SandboxRequest, SandboxResult


@dataclass(frozen=True, slots=True)
class DockerSandboxConfig:
    image: str
    runtime: str = "runc"
    docker_host: str | None = None
    network_name: str = "xhunter-internal"
    workspace: str = "/workspace"
    memory: str = "2g"
    cpus: float = 2.0

    def __post_init__(self) -> None:
        if not self.image or not self.network_name or not self.workspace:
            raise ValueError("Docker image, network, and workspace must not be empty")
        if self.cpus <= 0:
            raise ValueError("Docker CPU limit must be positive")


@dataclass(frozen=True, slots=True)
class DockerCommandResult:
    exit_code: int
    stdout: bytes = b""
    stderr: bytes = b""


class DockerCommandTransport(Protocol):
    async def run(
        self,
        command: Sequence[str],
        environment: Mapping[str, str],
        stdin: bytes | None = None,
        timeout_seconds: float = 30.0,
    ) -> DockerCommandResult:
        ...


class DockerSandbox:
    def __init__(
        self,
        config: DockerSandboxConfig,
        transport: DockerCommandTransport,
    ) -> None:
        self._config = config
        self._transport = transport
        self._container_name = f"xhunter-{uuid4().hex}"
        self._started = False
        self._lock = asyncio.Lock()

    async def execute(self, request: SandboxRequest) -> SandboxResult:
        if not request.command:
            return SandboxResult(2, stderr="command must not be empty")
        await self._ensure_started()
        command = ["docker"]
        command.extend(self._host_arguments())
        command.extend(("exec", "--interactive"))
        if request.working_directory is not None:
            command.extend(("--workdir", request.working_directory))
        for name, value in sorted(request.environment.items()):
            command.extend(("--env", f"{name}={value}"))
        command.append(self._container_name)
        command.extend(request.command)
        result = await self._transport.run(
            command,
            {},
            request.stdin,
            request.timeout_seconds,
        )
        return SandboxResult(
            result.exit_code,
            result.stdout.decode(errors="replace"),
            result.stderr.decode(errors="replace"),
            result.exit_code == 124,
        )

    async def close(self) -> None:
        async with self._lock:
            if not self._started:
                return
            command = ["docker"]
            command.extend(self._host_arguments())
            command.extend(("rm", "--force", self._container_name))
            await self._transport.run(command, {}, timeout_seconds=30)
            self._started = False

    async def _ensure_started(self) -> None:
        async with self._lock:
            if self._started:
                return
            await self._ensure_internal_network()
            command = ["docker"]
            command.extend(self._host_arguments())
            command.extend(
                (
                    "run",
                    "--detach",
                    "--name",
                    self._container_name,
                    "--network",
                    self._config.network_name,
                    "--runtime",
                    self._config.runtime,
                    "--memory",
                    self._config.memory,
                    "--cpus",
                    str(self._config.cpus),
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges",
                    "--workdir",
                    self._config.workspace,
                    self._config.image,
                    "sleep",
                    "infinity",
                )
            )
            result = await self._transport.run(command, {}, timeout_seconds=60)
            if result.exit_code != 0:
                raise RuntimeError(_error("failed to start Docker sandbox", result))
            self._started = True

    async def _ensure_internal_network(self) -> None:
        inspect = ["docker"]
        inspect.extend(self._host_arguments())
        inspect.extend(
            (
                "network",
                "inspect",
                "--format",
                "{{json .Internal}}",
                self._config.network_name,
            )
        )
        result = await self._transport.run(inspect, {}, timeout_seconds=30)
        if result.exit_code == 0:
            try:
                internal = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    "Docker network inspect returned invalid JSON"
                ) from exc
            if internal is not True:
                raise RuntimeError("configured Docker network is not internal")
            return

        create = ["docker"]
        create.extend(self._host_arguments())
        create.extend(
            ("network", "create", "--internal", self._config.network_name)
        )
        created = await self._transport.run(create, {}, timeout_seconds=30)
        if created.exit_code != 0:
            raise RuntimeError(_error("failed to create Docker network", created))

    def _host_arguments(self) -> tuple[str, ...]:
        if self._config.docker_host is None:
            return ()
        return ("--host", self._config.docker_host)


def _error(prefix: str, result: DockerCommandResult) -> str:
    detail = result.stderr.decode(errors="replace").strip()[:1000]
    return f"{prefix}: {detail}" if detail else prefix
