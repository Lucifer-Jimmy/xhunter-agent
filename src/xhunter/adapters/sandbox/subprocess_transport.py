"""Host control-plane transport for invoking the Docker CLI."""

import asyncio
import os
from collections.abc import Mapping, Sequence

from xhunter.adapters.sandbox.docker import DockerCommandResult


class SubprocessDockerTransport:
    async def run(
        self,
        command: Sequence[str],
        environment: Mapping[str, str],
        stdin: bytes | None = None,
        timeout_seconds: float = 30.0,
    ) -> DockerCommandResult:
        process_environment = {
            name: os.environ[name]
            for name in ("PATH", "HOME", "DOCKER_CONFIG")
            if name in os.environ
        }
        process_environment.update(environment)
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                env=process_environment,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, PermissionError, OSError) as exc:
            return DockerCommandResult(127, stderr=str(exc).encode())
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(stdin), timeout_seconds
            )
        except TimeoutError:
            process.kill()
            stdout, stderr = await process.communicate()
            return DockerCommandResult(
                124, stdout, stderr or b"Docker command timed out"
            )
        return DockerCommandResult(process.returncode or 0, stdout, stderr)
