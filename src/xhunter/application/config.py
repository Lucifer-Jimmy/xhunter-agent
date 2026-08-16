"""Standard-library configuration with explicit environment overrides."""

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BudgetConfig:
    mission_tool_calls: int = 100
    task_tool_calls: int = 30
    wall_clock_seconds: float = 3600.0
    mission_model_tokens: int = 1_000_000
    task_model_tokens: int = 200_000
    mission_model_cost: float = 100.0
    task_model_cost: float = 20.0


@dataclass(frozen=True, slots=True)
class ModelConfig:
    provider: str = "deepseek"
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-v4-pro"
    api_key: str = ""
    timeout_seconds: float = 120.0


@dataclass(frozen=True, slots=True)
class AppConfig:
    sandbox_provider: str = "local"
    sandbox_image: str = "xhunter/base:latest"
    sandbox_runtime: str = "runc"
    docker_host: str | None = None
    sandbox_network: str = "xhunter-internal"
    sandbox_workspace: str = "/workspace"
    allowed_targets: tuple[str, ...] = ()
    blocked_targets: tuple[str, ...] = ()
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    trace_path: Path = Path(".xhunter/session.jsonl")
    artifacts_provider: str = "local"
    artifacts_path: Path = Path(".xhunter/artifacts")
    checkpoint_provider: str = "file"
    checkpoint_path: Path = Path(".xhunter/checkpoints")
    storage_provider: str = "file"
    storage_path: Path = Path(".xhunter/storage")


def load_config(
    path: Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> AppConfig:
    values = os.environ if environment is None else environment
    document: dict[str, object] = {}
    if path is not None:
        with path.open("rb") as stream:
            document = tomllib.load(stream)

    sandbox = _section(document, "sandbox")
    policy = _section(document, "policy")
    budget = _section(document, "budget")
    tracing = _section(document, "tracing")
    model = _section(document, "model")
    artifacts = _section(document, "artifacts")
    checkpoint = _section(document, "checkpoint")
    storage = _section(document, "storage")
    return AppConfig(
        sandbox_provider=values.get(
            "XHUNTER_SANDBOX_PROVIDER", _string(sandbox, "provider", "local")
        ),
        sandbox_image=values.get(
            "XHUNTER_SANDBOX_IMAGE",
            _string(sandbox, "image", "xhunter/base:latest"),
        ),
        sandbox_runtime=values.get(
            "XHUNTER_SANDBOX_RUNTIME", _string(sandbox, "runtime", "runc")
        ),
        docker_host=values.get("XHUNTER_DOCKER_HOST")
        or _optional_string(sandbox, "docker_host"),
        sandbox_network=values.get(
            "XHUNTER_SANDBOX_NETWORK",
            _string(sandbox, "network", "xhunter-internal"),
        ),
        sandbox_workspace=values.get(
            "XHUNTER_SANDBOX_WORKSPACE",
            _string(sandbox, "workspace", "/workspace"),
        ),
        allowed_targets=_environment_list(
            values,
            "XHUNTER_ALLOWED_TARGETS",
            _string_list(policy, "allowed_targets"),
        ),
        blocked_targets=_environment_list(
            values,
            "XHUNTER_BLOCKED_TARGETS",
            _string_list(policy, "blocked_targets"),
        ),
        budget=BudgetConfig(
            mission_tool_calls=_environment_int(
                values,
                "XHUNTER_MISSION_TOOL_CALLS",
                _integer(budget, "mission_tool_calls", 100),
            ),
            task_tool_calls=_environment_int(
                values,
                "XHUNTER_TASK_TOOL_CALLS",
                _integer(budget, "task_tool_calls", 30),
            ),
            wall_clock_seconds=_environment_float(
                values,
                "XHUNTER_WALL_CLOCK_SECONDS",
                _number(budget, "wall_clock_seconds", 3600.0),
            ),
            mission_model_tokens=_environment_int(
                values,
                "XHUNTER_MISSION_MODEL_TOKENS",
                _integer(budget, "mission_model_tokens", 1_000_000),
            ),
            task_model_tokens=_environment_int(
                values,
                "XHUNTER_TASK_MODEL_TOKENS",
                _integer(budget, "task_model_tokens", 200_000),
            ),
            mission_model_cost=_environment_float(
                values,
                "XHUNTER_MISSION_MODEL_COST",
                _number(budget, "mission_model_cost", 100.0),
            ),
            task_model_cost=_environment_float(
                values,
                "XHUNTER_TASK_MODEL_COST",
                _number(budget, "task_model_cost", 20.0),
            ),
        ),
        model=ModelConfig(
            provider=values.get(
                "XHUNTER_MODEL_PROVIDER", _string(model, "provider", "deepseek")
            ),
            base_url=values.get(
                "XHUNTER_MODEL_BASE_URL",
                _string(model, "base_url", "https://api.deepseek.com/v1"),
            ),
            model=values.get(
                "XHUNTER_MODEL", _string(model, "model", "deepseek-v4-pro")
            ),
            api_key=values.get("XHUNTER_MODEL_API_KEY", ""),
            timeout_seconds=_environment_float(
                values,
                "XHUNTER_MODEL_TIMEOUT_SECONDS",
                _number(model, "timeout_seconds", 120.0),
            ),
        ),
        trace_path=Path(
            values.get(
                "XHUNTER_TRACE_PATH",
                _string(tracing, "path", ".xhunter/session.jsonl"),
            )
        ),
        artifacts_provider=values.get(
            "XHUNTER_ARTIFACTS_PROVIDER",
            _string(artifacts, "provider", "local"),
        ),
        artifacts_path=Path(
            values.get(
                "XHUNTER_ARTIFACTS_PATH",
                _string(artifacts, "path", ".xhunter/artifacts"),
            )
        ),
        checkpoint_provider=values.get(
            "XHUNTER_CHECKPOINT_PROVIDER",
            _string(checkpoint, "provider", "file"),
        ),
        checkpoint_path=Path(
            values.get(
                "XHUNTER_CHECKPOINT_PATH",
                _string(checkpoint, "path", ".xhunter/checkpoints"),
            )
        ),
        storage_provider=values.get(
            "XHUNTER_STORAGE_PROVIDER", _string(storage, "provider", "file")
        ),
        storage_path=Path(
            values.get(
                "XHUNTER_STORAGE_PATH",
                _string(storage, "path", ".xhunter/storage"),
            )
        ),
    )


def _section(document: dict[str, object], name: str) -> dict[str, object]:
    value = document.get(name, {})
    if not isinstance(value, dict):
        raise ValueError(f"configuration section must be a table: {name}")
    return value


def _string(section: dict[str, object], name: str, default: str) -> str:
    value = section.get(name, default)
    if not isinstance(value, str):
        raise ValueError(f"configuration value must be a string: {name}")
    return value


def _optional_string(section: dict[str, object], name: str) -> str | None:
    value = section.get(name)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"configuration value must be a string: {name}")
    return value


def _string_list(section: dict[str, object], name: str) -> tuple[str, ...]:
    value = section.get(name, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"configuration value must be a string list: {name}")
    return tuple(value)


def _integer(section: dict[str, object], name: str, default: int) -> int:
    value = section.get(name, default)
    if not isinstance(value, int):
        raise ValueError(f"configuration value must be an integer: {name}")
    return value


def _number(section: dict[str, object], name: str, default: float) -> float:
    value = section.get(name, default)
    if not isinstance(value, int | float):
        raise ValueError(f"configuration value must be numeric: {name}")
    return float(value)


def _environment_list(
    environment: Mapping[str, str], name: str, default: tuple[str, ...]
) -> tuple[str, ...]:
    value = environment.get(name)
    if value is None:
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _environment_int(
    environment: Mapping[str, str], name: str, default: int
) -> int:
    value = environment.get(name)
    return default if value is None else int(value)


def _environment_float(
    environment: Mapping[str, str], name: str, default: float
) -> float:
    value = environment.get(name)
    return default if value is None else float(value)
