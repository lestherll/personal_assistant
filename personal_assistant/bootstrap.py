from __future__ import annotations

from personal_assistant.providers import (
    AnthropicProvider,
    OllamaConfig,
    OllamaProvider,
    ProviderRegistry,
)


def build_registry() -> ProviderRegistry:
    """Create and configure the default provider registry."""
    registry = ProviderRegistry()
    registry.register(AnthropicProvider())
    registry.register(OllamaProvider(OllamaConfig(default_model="qwen2.5:14b")), default=True)
    return registry
