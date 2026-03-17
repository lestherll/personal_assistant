"""Unit tests for api/routers/providers.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx


async def test_list_providers_returns_200(
    api_client: httpx.AsyncClient, mock_provider_registry: MagicMock
) -> None:
    response = await api_client.get("/providers/")
    assert response.status_code == 200


async def test_list_providers_returns_all_registered(
    api_client: httpx.AsyncClient, mock_provider_registry: MagicMock
) -> None:
    mock_provider_registry.list.return_value = ["anthropic", "ollama"]

    anthropic_provider = MagicMock()
    anthropic_provider.name = "anthropic"
    anthropic_provider.default_model = "claude-sonnet-4-6"

    ollama_provider = MagicMock()
    ollama_provider.name = "ollama"
    ollama_provider.default_model = "llama3.2"

    def _get(name: str | None = None) -> MagicMock:
        return anthropic_provider if name == "anthropic" else ollama_provider

    mock_provider_registry.get.side_effect = _get

    response = await api_client.get("/providers/")
    data = response.json()
    assert len(data) == 2
    names = {p["name"] for p in data}
    assert names == {"anthropic", "ollama"}


async def test_list_providers_includes_default_model(
    api_client: httpx.AsyncClient, mock_provider_registry: MagicMock
) -> None:
    mock_provider_registry.list.return_value = ["anthropic"]

    provider = MagicMock()
    provider.name = "anthropic"
    provider.default_model = "claude-sonnet-4-6"
    mock_provider_registry.get.return_value = provider

    response = await api_client.get("/providers/")
    data = response.json()
    assert data[0]["default_model"] == "claude-sonnet-4-6"


async def test_list_provider_models_returns_200(
    api_client: httpx.AsyncClient, mock_provider_registry: MagicMock
) -> None:
    provider = MagicMock()
    provider.name = "anthropic"
    provider.list_models = AsyncMock(return_value=["claude-sonnet-4-6", "claude-opus-4-6"])
    mock_provider_registry.get.return_value = provider

    response = await api_client.get("/providers/anthropic/models")
    assert response.status_code == 200


async def test_list_provider_models_returns_models(
    api_client: httpx.AsyncClient, mock_provider_registry: MagicMock
) -> None:
    provider = MagicMock()
    provider.name = "anthropic"
    provider.list_models = AsyncMock(return_value=["claude-sonnet-4-6", "claude-opus-4-6"])
    mock_provider_registry.get.return_value = provider

    response = await api_client.get("/providers/anthropic/models")
    data = response.json()
    assert data["name"] == "anthropic"
    assert "claude-sonnet-4-6" in data["models"]
    assert "claude-opus-4-6" in data["models"]


async def test_list_provider_models_not_found_returns_404(
    api_client: httpx.AsyncClient, mock_provider_registry: MagicMock
) -> None:
    mock_provider_registry.get.side_effect = KeyError("unknown")
    response = await api_client.get("/providers/unknown/models")
    assert response.status_code == 404


async def test_provider_health_returns_200(
    api_client: httpx.AsyncClient, mock_provider_registry: MagicMock
) -> None:
    provider = MagicMock()
    provider.health = AsyncMock(return_value={"status": "ok"})
    mock_provider_registry.get.side_effect = None
    mock_provider_registry.get.return_value = provider

    response = await api_client.get("/providers/anthropic/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_provider_health_returns_error_detail(
    api_client: httpx.AsyncClient, mock_provider_registry: MagicMock
) -> None:
    provider = MagicMock()
    provider.health = AsyncMock(return_value={"status": "error", "detail": "unreachable"})
    mock_provider_registry.get.side_effect = None
    mock_provider_registry.get.return_value = provider

    response = await api_client.get("/providers/ollama/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert data["detail"] == "unreachable"


async def test_provider_health_not_found_returns_404(
    api_client: httpx.AsyncClient, mock_provider_registry: MagicMock
) -> None:
    mock_provider_registry.get.side_effect = KeyError("unknown")
    response = await api_client.get("/providers/unknown/health")
    assert response.status_code == 404
