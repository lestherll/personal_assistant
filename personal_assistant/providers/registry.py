from personal_assistant.providers.base import AIProvider


class ProviderRegistry:
    """Central registry for AI providers.

    Usage::

        registry = ProviderRegistry()
        registry.register(AnthropicProvider(AnthropicConfig()), default=True)
        registry.register(OllamaProvider(OllamaConfig()))

        model = registry.get("anthropic").get_model()
        model = registry.get().get_model()          # uses default provider
    """

    def __init__(self) -> None:
        self._providers: dict[str, AIProvider] = {}
        self._default: str | None = None

    def register(self, provider: AIProvider, default: bool = False) -> None:
        """Register a provider. The first registered provider becomes the default
        unless another is explicitly set or default=True is passed."""
        self._providers[provider.name] = provider
        if default or self._default is None:
            self._default = provider.name

    def get(self, name: str | None = None) -> AIProvider:
        """Retrieve a provider by name, or the default if name is omitted."""
        target = name or self._default
        if not target:
            raise RuntimeError("No providers registered.")
        if target not in self._providers:
            raise KeyError(f"Provider '{target}' is not registered. Available: {self.list()}")
        return self._providers[target]

    def set_default(self, name: str) -> None:
        if name not in self._providers:
            raise KeyError(f"Provider '{name}' is not registered.")
        self._default = name

    @property
    def default(self) -> str | None:
        return self._default

    def list(self) -> list[str]:
        return list(self._providers.keys())

    def __repr__(self) -> str:
        return f"ProviderRegistry(providers={self.list()}, default={self._default!r})"
