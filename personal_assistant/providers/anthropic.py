import os
from dataclasses import dataclass

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel

from personal_assistant.providers.base import AIProvider, ProviderConfig


@dataclass
class AnthropicConfig(ProviderConfig):
    name: str = "anthropic"
    default_model: str = "claude-opus-4-6"
    api_key: str | None = None  # Falls back to ANTHROPIC_API_KEY env var
    temperature: float = 0
    max_tokens: int = 8096


class AnthropicProvider(AIProvider):
    """Anthropic/Claude provider via langchain-anthropic."""

    def __init__(self, config: AnthropicConfig | None = None) -> None:
        super().__init__(config or AnthropicConfig())
        self.config: AnthropicConfig

    def get_model(self, model: str | None = None, **kwargs) -> BaseChatModel:
        return ChatAnthropic(
            model=model or self.config.default_model,
            api_key=self.config.api_key or os.getenv("ANTHROPIC_API_KEY"),
            temperature=kwargs.pop("temperature", self.config.temperature),
            max_tokens=kwargs.pop("max_tokens", self.config.max_tokens),
            **kwargs,
        )
