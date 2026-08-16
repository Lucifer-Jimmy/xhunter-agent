"""Configuration-driven model provider construction."""

from xhunter.adapters.models import (
    OpenAICompatibleConfig,
    OpenAICompatibleModelProvider,
)
from xhunter.application.config import ModelConfig
from xhunter.contracts.model import ModelProvider


def build_model_provider(config: ModelConfig) -> ModelProvider:
    if config.provider not in {"deepseek", "openai-compatible"}:
        raise ValueError(f"unsupported model provider: {config.provider}")
    return OpenAICompatibleModelProvider(
        OpenAICompatibleConfig(
            base_url=config.base_url,
            api_key=config.api_key,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
        )
    )
