from dataclasses import dataclass
from typing import Any

import httpx
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

    async def list_models(self) -> list[str]:
        """Query the local Ollama instance for available models.

        Falls back to [default_model] if Ollama is unreachable or returns an error.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.config.base_url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                return models if models else [self.default_model]
        except Exception:
            return [self.default_model]

    def get_model(self, model: str | None = None, **kwargs: Any) -> BaseChatModel:
        return ChatOllama(
            model=model or self.config.default_model,
            base_url=self.config.base_url,
            temperature=kwargs.pop("temperature", self.config.temperature),
            **kwargs,
        )
