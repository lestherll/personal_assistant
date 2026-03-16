from dataclasses import dataclass
from typing import Any, ClassVar

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from pydantic import SecretStr

from personal_assistant.config import get_settings
from personal_assistant.providers.base import AIProvider, ProviderConfig


@dataclass
class AnthropicConfig(ProviderConfig):
    name: str = "anthropic"
    default_model: str = "claude-sonnet-4-6"
    api_key: str | None = None  # Falls back to ANTHROPIC_API_KEY env var
    temperature: float = 0
    max_tokens: int = 8096


class AnthropicProvider(AIProvider):
    """Anthropic/Claude provider via langchain-anthropic."""

    def __init__(self, config: AnthropicConfig | None = None) -> None:
        super().__init__(config or AnthropicConfig())
        self.config: AnthropicConfig

    _KNOWN_MODELS: ClassVar[list[str]] = [
        "claude-opus-4-6",
        "claude-sonnet-4-6",
        "claude-haiku-4-5-20251001",
        "claude-opus-4-5",
        "claude-sonnet-4-5",
        "claude-haiku-4-5",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
    ]

    async def list_models(self) -> list[str]:
        return list(self._KNOWN_MODELS)

    def get_model(self, model: str | None = None, **kwargs: Any) -> BaseChatModel:
        raw_key = self.config.api_key or get_settings().anthropic_api_key
        extra: dict[str, Any] = {}
        if raw_key:
            extra["api_key"] = SecretStr(raw_key)
        return ChatAnthropic(  # type: ignore[call-arg]
            model=model or self.config.default_model,
            temperature=kwargs.pop("temperature", self.config.temperature),
            max_tokens=kwargs.pop("max_tokens", self.config.max_tokens),
            **extra,
            **kwargs,
        )
