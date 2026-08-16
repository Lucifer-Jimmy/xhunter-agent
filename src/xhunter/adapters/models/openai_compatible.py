"""OpenAI-compatible chat completion adapter for control-plane model calls."""

import asyncio
import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from xhunter.contracts.model import (
    Message,
    ModelRequest,
    ModelResponse,
    ToolCall,
    Usage,
)


class ModelProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OpenAICompatibleConfig:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if not self.base_url.startswith(("https://", "http://")):
            raise ValueError("model base_url must use http or https")
        if not self.api_key:
            raise ValueError("model api_key must not be empty")
        if not self.model:
            raise ValueError("model name must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("model timeout must be positive")


class JsonTransport(Protocol):
    async def post(
        self,
        url: str,
        headers: Mapping[str, str],
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        ...


class UrllibJsonTransport:
    async def post(
        self,
        url: str,
        headers: Mapping[str, str],
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        return await asyncio.to_thread(
            self._post, url, headers, payload, timeout_seconds
        )

    def _post(
        self,
        url: str,
        headers: Mapping[str, str],
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers=dict(headers),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                content = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:1000]
            raise ModelProviderError(
                f"model endpoint returned HTTP {exc.code}: {detail}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ModelProviderError(f"model endpoint request failed: {exc}") from exc
        try:
            value = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ModelProviderError("model endpoint returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise ModelProviderError("model endpoint JSON root must be an object")
        return value


class OpenAICompatibleModelProvider:
    def __init__(
        self,
        config: OpenAICompatibleConfig,
        transport: JsonTransport | None = None,
    ) -> None:
        self._config = config
        self._transport = transport or UrllibJsonTransport()

    async def generate(self, request: ModelRequest) -> ModelResponse:
        payload = _request_payload(self._config.model, request)
        response = await self._transport.post(
            f"{self._config.base_url.rstrip('/')}/chat/completions",
            {
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            payload,
            self._config.timeout_seconds,
        )
        return _response_dto(response)


def _request_payload(model: str, request: ModelRequest) -> dict[str, object]:
    messages: list[dict[str, str]] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.extend(_message_payload(message) for message in request.messages)
    payload: dict[str, object] = {"model": model, "messages": messages}
    if request.tools:
        payload["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": spec.capability,
                    "description": spec.description,
                    "parameters": spec.input_schema,
                },
            }
            for spec in request.tools
        ]
    return payload


def _message_payload(message: Message) -> dict[str, str]:
    return {"role": message.role, "content": message.content}


def _response_dto(response: dict[str, object]) -> ModelResponse:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ModelProviderError("model response has no valid choice")
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, dict):
        raise ModelProviderError("model response choice has no message")
    content = message.get("content")
    if content is not None and not isinstance(content, str):
        raise ModelProviderError("model response content must be a string or null")
    calls = _tool_calls(message.get("tool_calls", []))
    finish_reason = choice.get("finish_reason", "stop")
    if not isinstance(finish_reason, str):
        finish_reason = "unknown"
    return ModelResponse(
        content=content,
        tool_calls=calls,
        usage=_usage(response.get("usage", {})),
        finish_reason=finish_reason,
    )


def _tool_calls(value: object) -> tuple[ToolCall, ...]:
    if not isinstance(value, list):
        raise ModelProviderError("model tool_calls must be a list")
    calls: list[ToolCall] = []
    for item in value:
        if not isinstance(item, dict):
            raise ModelProviderError("model tool call must be an object")
        function = item.get("function")
        if not isinstance(function, dict):
            raise ModelProviderError("model tool call has no function")
        call_id = item.get("id")
        name = function.get("name")
        arguments = function.get("arguments", "{}")
        if not isinstance(call_id, str) or not isinstance(name, str):
            raise ModelProviderError("model tool call id and name must be strings")
        if not isinstance(arguments, str):
            raise ModelProviderError("model tool arguments must be JSON text")
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise ModelProviderError(
                "model tool arguments contain invalid JSON"
            ) from exc
        if not isinstance(parsed, dict):
            raise ModelProviderError("model tool arguments must decode to an object")
        calls.append(ToolCall(call_id, name, parsed))
    return tuple(calls)


def _usage(value: object) -> Usage:
    if not isinstance(value, dict):
        return Usage()
    return Usage(
        input_tokens=_nonnegative_int(value.get("prompt_tokens")),
        output_tokens=_nonnegative_int(value.get("completion_tokens")),
    )


def _nonnegative_int(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0
