from abc import ABC, abstractmethod
from dataclasses import dataclass

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
    def get_model(self, model: str | None = None, **kwargs) -> BaseChatModel:
        """Return a configured LangChain chat model instance.

        Args:
            model: Model name/ID to use. Defaults to the provider's default_model.
            **kwargs: Extra arguments forwarded to the underlying model constructor.
        """
        ...

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(name={self.name!r}, default_model={self.default_model!r})"
        )
