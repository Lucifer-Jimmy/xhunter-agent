import unittest

from xhunter.adapters.models import (
    ModelProviderError,
    OpenAICompatibleConfig,
    OpenAICompatibleModelProvider,
)
from xhunter.application.config import ModelConfig
from xhunter.application.models import build_model_provider
from xhunter.contracts.model import Message, ModelRequest
from xhunter.contracts.tool import ToolSpec


class FakeJsonTransport:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[
            tuple[str, dict[str, str], dict[str, object], float]
        ] = []

    async def post(self, url, headers, payload, timeout_seconds):
        self.calls.append((url, dict(headers), payload, timeout_seconds))
        choices = self.response.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message")
            if isinstance(message, dict):
                calls = message.get("tool_calls")
                tools = payload.get("tools")
                if isinstance(calls, list) and isinstance(tools, list):
                    function = calls[0].get("function")
                    tool = tools[0]
                    if isinstance(function, dict) and isinstance(tool, dict):
                        tool_function = tool.get("function")
                        if isinstance(tool_function, dict):
                            function["name"] = tool_function["name"]
        return self.response


class OpenAICompatibleProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_converts_request_and_response_at_adapter_boundary(self) -> None:
        transport = FakeJsonTransport(
            {
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "function": {
                                        "name": "network.http",
                                        "arguments": '{"url":"http://target.local"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 7},
            }
        )
        provider = OpenAICompatibleModelProvider(
            OpenAICompatibleConfig(
                "https://model.example/v1", "top-secret", "deepseek-v4-pro", 45
            ),
            transport,
        )
        response = await provider.generate(
            ModelRequest(
                system_prompt="system",
                messages=(Message("user", "inspect target"),),
                tools=(
                    ToolSpec(
                        "network.http",
                        "Send HTTP request",
                        {
                            "type": "object",
                            "properties": {"url": {"type": "string"}},
                        },
                    ),
                ),
            )
        )

        url, headers, payload, timeout = transport.calls[0]
        messages = payload["messages"]
        tools = payload["tools"]
        assert isinstance(messages, list) and isinstance(messages[0], dict)
        assert isinstance(tools, list) and isinstance(tools[0], dict)
        function = tools[0]["function"]
        assert isinstance(function, dict)
        self.assertEqual(url, "https://model.example/v1/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer top-secret")
        self.assertEqual(messages[0]["role"], "system")
        self.assertTrue(function["name"].startswith("xh_network_http_"))
        self.assertEqual(timeout, 45)
        self.assertEqual(response.tool_calls[0].capability, "network.http")
        self.assertEqual(response.tool_calls[0].arguments["url"], "http://target.local")
        self.assertEqual(response.usage.input_tokens, 12)

    async def test_invalid_tool_argument_json_fails_closed(self) -> None:
        provider = OpenAICompatibleModelProvider(
            OpenAICompatibleConfig("https://model.example/v1", "secret", "model"),
            FakeJsonTransport(
                {
                    "choices": [
                        {
                            "message": {
                                "tool_calls": [
                                    {
                                        "id": "call-1",
                                        "function": {
                                            "name": "code.python",
                                            "arguments": "not-json",
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
            ),
        )
        with self.assertRaises(ModelProviderError):
            await provider.generate(ModelRequest())


class ModelCompositionTests(unittest.TestCase):
    def test_deepseek_uses_openai_compatible_adapter(self) -> None:
        provider = build_model_provider(
            ModelConfig(api_key="secret", model="deepseek-v4-flash")
        )
        self.assertIsInstance(provider, OpenAICompatibleModelProvider)

    def test_unknown_provider_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_model_provider(ModelConfig(provider="unknown", api_key="secret"))

    def test_missing_api_key_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_model_provider(ModelConfig())
