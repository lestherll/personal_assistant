from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel


@dataclass
class ProviderConfig:
    name: str
    default_model: str


class AIProvider(ABC):
    """Base class for all AI providers.

    A provider wraps a specific LLM backend (Anthropic, Ollama, OpenAI, etc.)
    and knows how to produce a LangChain-compatible chat model from it.
    Register providers with the ProviderRegistry and reference them by name
    in AgentConfig.
    """

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def default_model(self) -> str:
        return self.config.default_model

    @abstractmethod
    def get_model(self, model: str | None = None, **kwargs: Any) -> BaseChatModel:
        """Return a configured LangChain chat model instance.

        Args:
            model: Model name/ID to use. Defaults to the provider's default_model.
            **kwargs: Extra arguments forwarded to the underlying model constructor.
        """
        ...

    async def health(self) -> dict[str, str]:
        """Check provider health. Returns {"status": "ok"} or {"status": "error", "detail": ...}."""
        return {"status": "ok"}

    async def list_models(self) -> list[str]:
        """Return a list of available model names for this provider.

        Subclasses may override this to query the backend dynamically.
        The default implementation returns only the configured default model.
        """
        return [self.default_model]

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(name={self.name!r}, default_model={self.default_model!r})"
        )
