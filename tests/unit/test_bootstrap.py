"""Unit tests for personal_assistant.bootstrap."""

from __future__ import annotations

from unittest.mock import patch

from personal_assistant.bootstrap import build_registry
from personal_assistant.providers.registry import ProviderRegistry


def test_build_registry_returns_provider_registry() -> None:
    with (
        patch("personal_assistant.bootstrap.AnthropicProvider"),
        patch("personal_assistant.bootstrap.OllamaProvider"),
    ):
        registry = build_registry()
    assert isinstance(registry, ProviderRegistry)


def test_build_registry_registers_anthropic() -> None:
    with (
        patch("personal_assistant.bootstrap.AnthropicProvider") as mock_anthropic,
        patch("personal_assistant.bootstrap.OllamaProvider"),
    ):
        mock_anthropic.return_value.name = "anthropic"
        registry = build_registry()
    assert "anthropic" in registry.list()


def test_build_registry_registers_ollama() -> None:
    with (
        patch("personal_assistant.bootstrap.AnthropicProvider"),
        patch("personal_assistant.bootstrap.OllamaProvider") as mock_ollama,
    ):
        mock_ollama.return_value.name = "ollama"
        registry = build_registry()
    assert "ollama" in registry.list()


def test_build_registry_sets_ollama_as_default() -> None:
    with (
        patch("personal_assistant.bootstrap.AnthropicProvider"),
        patch("personal_assistant.bootstrap.OllamaProvider") as mock_ollama,
    ):
        mock_ollama.return_value.name = "ollama"
        registry = build_registry()
    assert registry.default == "ollama"
