"""Configuration-driven construction with fail-closed local sandbox gating."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from xhunter.adapters.sandbox import LocalSandbox
from xhunter.contracts.sandbox import Sandbox

_UNSAFE_LOCAL_ENV = "XHUNTER_ALLOW_UNSAFE_LOCAL_SANDBOX"


class UnsafeLocalSandboxError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SandboxConfig:
    provider: str = "local"


def build_mission_sandbox(
    config: SandboxConfig,
    environment: Mapping[str, str] | None = None,
) -> Sandbox:
    values = os.environ if environment is None else environment
    if config.provider == "local":
        if values.get(_UNSAFE_LOCAL_ENV) != "1":
            raise UnsafeLocalSandboxError(
                "LocalSandbox is unsafe for real missions; set "
                f"{_UNSAFE_LOCAL_ENV}=1 only for explicit local development"
            )
        return LocalSandbox(values)
    raise ValueError(f"unsupported sandbox provider: {config.provider}")
