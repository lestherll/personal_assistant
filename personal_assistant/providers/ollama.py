from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from personal_assistant.providers.base import AIProvider, ProviderConfig


@dataclass
class OllamaConfig(ProviderConfig):
    name: str = "ollama"
    default_model: str = "llama3.2"
    base_url: str = "http://localhost:11434"
    temperature: float = 0


class OllamaProvider(AIProvider):
    """Ollama provider for running models locally via langchain-ollama.

    Requires Ollama to be running: https://ollama.com
    Pull a model first: `ollama pull llama3.2`
    """

    def __init__(self, config: OllamaConfig | None = None) -> None:
        super().__init__(config or OllamaConfig())
        self.config: OllamaConfig

    def get_model(self, model: str | None = None, **kwargs: Any) -> BaseChatModel:
        return ChatOllama(
            model=model or self.config.default_model,
            base_url=self.config.base_url,
            temperature=kwargs.pop("temperature", self.config.temperature),
            **kwargs,
        )
