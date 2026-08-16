"""Unsafe local subprocess adapter for tests and explicit local development."""

import asyncio
import os
from collections.abc import Mapping

from xhunter.contracts.sandbox import SandboxRequest, SandboxResult

_PASSTHROUGH_ENVIRONMENT = (
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "TMPDIR",
    "WINDIR",
)


class LocalSandbox:
    """Execute argv locally without a shell and without inheriting credentials."""

    def __init__(self, host_environment: Mapping[str, str] | None = None) -> None:
        source = os.environ if host_environment is None else host_environment
        self._base_environment = {
            name: source[name] for name in _PASSTHROUGH_ENVIRONMENT if name in source
        }

    async def execute(self, request: SandboxRequest) -> SandboxResult:
        if not request.command:
            return SandboxResult(exit_code=2, stderr="command must not be empty")
        if request.timeout_seconds <= 0:
            return SandboxResult(exit_code=2, stderr="timeout_seconds must be positive")

        environment = dict(self._base_environment)
        environment.update(request.environment)
        try:
            process = await asyncio.create_subprocess_exec(
                *request.command,
                cwd=request.working_directory,
                env=environment,
                stdin=(
                    asyncio.subprocess.PIPE
                    if request.stdin is not None
                    else asyncio.subprocess.DEVNULL
                ),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, NotADirectoryError, PermissionError, OSError) as exc:
            return SandboxResult(exit_code=127, stderr=str(exc))

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(request.stdin), timeout=request.timeout_seconds
            )
        except TimeoutError:
            process.kill()
            stdout, stderr = await process.communicate()
            return SandboxResult(
                exit_code=124,
                stdout=_decode(stdout),
                stderr=_decode(stderr) or "command timed out",
                timed_out=True,
            )

        return SandboxResult(
            exit_code=process.returncode or 0,
            stdout=_decode(stdout),
            stderr=_decode(stderr),
        )

    async def close(self) -> None:
        return None


def _decode(content: bytes) -> str:
    return content.decode("utf-8", errors="replace")
