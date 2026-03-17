"""Unit tests for AI provider implementations."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from langchain_core.language_models import BaseChatModel

from personal_assistant.providers.anthropic import AnthropicConfig, AnthropicProvider
from personal_assistant.providers.base import AIProvider, ProviderConfig
from personal_assistant.providers.ollama import OllamaConfig, OllamaProvider

# ---------------------------------------------------------------------------
# Minimal concrete subclass for testing AIProvider base
# ---------------------------------------------------------------------------


class ConcreteProvider(AIProvider):
    def get_model(self, model: str | None = None, **kwargs: Any) -> BaseChatModel:
        return MagicMock(spec=BaseChatModel)


class TestAIProviderBase:
    def test_name_property(self):
        config = ProviderConfig(name="test-provider", default_model="test-model")
        provider = ConcreteProvider(config)
        assert provider.name == "test-provider"

    def test_default_model_property(self):
        config = ProviderConfig(name="test-provider", default_model="my-model")
        provider = ConcreteProvider(config)
        assert provider.default_model == "my-model"

    def test_repr(self):
        config = ProviderConfig(name="test-provider", default_model="my-model")
        provider = ConcreteProvider(config)
        r = repr(provider)
        assert "test-provider" in r
        assert "my-model" in r

    async def test_list_models_default_returns_default_model(self):
        config = ProviderConfig(name="test-provider", default_model="my-model")
        provider = ConcreteProvider(config)
        models = await provider.list_models()
        assert models == ["my-model"]


# ---------------------------------------------------------------------------
# AnthropicProvider
# ---------------------------------------------------------------------------


class TestAnthropicProvider:
    def test_get_model_uses_default_model_when_none(self):
        provider = AnthropicProvider(AnthropicConfig(api_key="sk-test"))
        with patch("personal_assistant.providers.anthropic.ChatAnthropic") as mock_cls:
            mock_cls.return_value = MagicMock(spec=BaseChatModel)
            provider.get_model()
            call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-6"

    def test_get_model_uses_custom_model(self):
        provider = AnthropicProvider(AnthropicConfig(api_key="sk-test"))
        with patch("personal_assistant.providers.anthropic.ChatAnthropic") as mock_cls:
            mock_cls.return_value = MagicMock(spec=BaseChatModel)
            provider.get_model("claude-opus-4-6")
            call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["model"] == "claude-opus-4-6"

    def test_get_model_uses_api_key_from_config(self):
        provider = AnthropicProvider(AnthropicConfig(api_key="sk-from-config"))
        with patch("personal_assistant.providers.anthropic.ChatAnthropic") as mock_cls:
            mock_cls.return_value = MagicMock(spec=BaseChatModel)
            provider.get_model()
            call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["api_key"].get_secret_value() == "sk-from-config"

    def test_get_model_falls_back_to_env_var(self):
        from personal_assistant.config import Settings

        mock_settings = Settings(anthropic_api_key="sk-from-env")
        provider = AnthropicProvider(AnthropicConfig())  # No api_key in config
        with patch(
            "personal_assistant.providers.anthropic.get_settings", return_value=mock_settings
        ):
            with patch("personal_assistant.providers.anthropic.ChatAnthropic") as mock_cls:
                mock_cls.return_value = MagicMock(spec=BaseChatModel)
                provider.get_model()
                call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["api_key"].get_secret_value() == "sk-from-env"

    def test_get_model_no_api_key_omits_key_arg(self):
        from personal_assistant.config import Settings

        mock_settings = Settings(anthropic_api_key=None)
        provider = AnthropicProvider(AnthropicConfig())  # No api_key anywhere
        with patch(
            "personal_assistant.providers.anthropic.get_settings", return_value=mock_settings
        ):
            with patch("personal_assistant.providers.anthropic.ChatAnthropic") as mock_cls:
                mock_cls.return_value = MagicMock(spec=BaseChatModel)
                provider.get_model()
                call_kwargs = mock_cls.call_args.kwargs
        assert "api_key" not in call_kwargs

    def test_get_model_passes_temperature_kwarg(self):
        provider = AnthropicProvider(AnthropicConfig(api_key="sk-test"))
        with patch("personal_assistant.providers.anthropic.ChatAnthropic") as mock_cls:
            mock_cls.return_value = MagicMock(spec=BaseChatModel)
            provider.get_model(temperature=0.7)
            call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["temperature"] == 0.7

    def test_get_model_passes_max_tokens_kwarg(self):
        provider = AnthropicProvider(AnthropicConfig(api_key="sk-test"))
        with patch("personal_assistant.providers.anthropic.ChatAnthropic") as mock_cls:
            mock_cls.return_value = MagicMock(spec=BaseChatModel)
            provider.get_model(max_tokens=1024)
            call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["max_tokens"] == 1024

    async def test_list_models_returns_known_claude_models(self):
        provider = AnthropicProvider(AnthropicConfig(api_key="sk-test"))
        models = await provider.list_models()
        assert "claude-sonnet-4-6" in models
        assert "claude-opus-4-6" in models
        assert len(models) > 1

    async def test_list_models_includes_default_model(self):
        provider = AnthropicProvider(AnthropicConfig(api_key="sk-test"))
        models = await provider.list_models()
        assert provider.default_model in models


# ---------------------------------------------------------------------------
# OllamaProvider
# ---------------------------------------------------------------------------


class TestOllamaProvider:
    def test_get_model_uses_default_model_when_none(self):
        provider = OllamaProvider(OllamaConfig())
        with patch("personal_assistant.providers.ollama.ChatOllama") as mock_cls:
            mock_cls.return_value = MagicMock(spec=BaseChatModel)
            provider.get_model()
            call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["model"] == "llama3.2"

    def test_get_model_uses_base_url(self):
        provider = OllamaProvider(OllamaConfig(base_url="http://custom:11434"))
        with patch("personal_assistant.providers.ollama.ChatOllama") as mock_cls:
            mock_cls.return_value = MagicMock(spec=BaseChatModel)
            provider.get_model()
            call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["base_url"] == "http://custom:11434"

    def test_get_model_passes_temperature_kwarg(self):
        provider = OllamaProvider(OllamaConfig())
        with patch("personal_assistant.providers.ollama.ChatOllama") as mock_cls:
            mock_cls.return_value = MagicMock(spec=BaseChatModel)
            provider.get_model(temperature=0.5)
            call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["temperature"] == 0.5

    async def test_list_models_queries_ollama_api(self):
        provider = OllamaProvider(OllamaConfig())
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "llama3.2"}, {"name": "qwen2.5"}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "personal_assistant.providers.ollama.httpx.AsyncClient", return_value=mock_client
        ):
            models = await provider.list_models()

        assert "llama3.2" in models
        assert "qwen2.5" in models

    async def test_list_models_falls_back_on_error(self):
        provider = OllamaProvider(OllamaConfig())

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with patch(
            "personal_assistant.providers.ollama.httpx.AsyncClient", return_value=mock_client
        ):
            models = await provider.list_models()

        assert models == [provider.default_model]

    async def test_list_models_falls_back_on_empty_response(self):
        provider = OllamaProvider(OllamaConfig())
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "personal_assistant.providers.ollama.httpx.AsyncClient", return_value=mock_client
        ):
            models = await provider.list_models()

        assert models == [provider.default_model]


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------


class TestBaseProviderHealth:
    async def test_default_health_returns_ok(self):
        config = ProviderConfig(name="test", default_model="m1")
        provider = ConcreteProvider(config)
        result = await provider.health()
        assert result == {"status": "ok"}


class TestOllamaHealth:
    async def test_health_ok(self):
        provider = OllamaProvider(OllamaConfig())
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "personal_assistant.providers.ollama.httpx.AsyncClient", return_value=mock_client
        ):
            result = await provider.health()

        assert result == {"status": "ok"}

    async def test_health_error(self):
        provider = OllamaProvider(OllamaConfig())

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with patch(
            "personal_assistant.providers.ollama.httpx.AsyncClient", return_value=mock_client
        ):
            result = await provider.health()

        assert result["status"] == "error"
        assert "Connection refused" in result["detail"]
