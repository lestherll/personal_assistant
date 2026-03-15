"""Shared fixtures for api unit tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from api.dependencies import (
    DEV_USER,
    get_agent_service,
    get_current_user,
    get_db_session,
    get_provider_registry,
    get_workspace_service,
)
from api.exception_handlers import register_exception_handlers
from api.routers import agents, providers, workspaces
from personal_assistant.services.views import (
    AgentConfigView,
    AgentView,
    WorkspaceDetailView,
    WorkspaceView,
)

# ---------------------------------------------------------------------------
# View builders (shared across router test modules)
# ---------------------------------------------------------------------------


def make_agent_view(name: str = "Assistant", **overrides: Any) -> AgentView:
    defaults: dict[str, Any] = {
        "config": AgentConfigView(
            name=name,
            description="General agent",
            system_prompt="You are helpful.",
            provider="ollama",
            model="qwen2.5:14b",
            allowed_tools=[],
        ),
        "tools": [],
        "llm_info": {"provider": "ollama", "model": "qwen2.5:14b", "source": "registry"},
    }
    defaults.update(overrides)
    return AgentView(**defaults)


def make_workspace_view(name: str = "ws1", **overrides: Any) -> WorkspaceView:
    defaults: dict[str, Any] = {
        "name": name,
        "description": "A workspace",
        "metadata": {},
        "agents": [],
        "tools": [],
    }
    defaults.update(overrides)
    return WorkspaceView(**defaults)


def make_workspace_detail_view(name: str = "ws1") -> WorkspaceDetailView:
    return WorkspaceDetailView(
        name=name,
        description="A workspace",
        metadata={},
        agents=[make_agent_view()],
        tools=[],
    )


# ---------------------------------------------------------------------------
# Service mocks
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_workspace_service() -> MagicMock:
    svc = MagicMock()
    svc.chat = AsyncMock()
    svc.stream_chat = AsyncMock()
    return svc


@pytest.fixture
def mock_agent_service() -> MagicMock:
    svc = MagicMock()
    svc.run_agent = AsyncMock()
    svc.stream_agent = AsyncMock()
    return svc


@pytest.fixture
def mock_provider_registry() -> MagicMock:
    from personal_assistant.providers.registry import ProviderRegistry

    registry = MagicMock(spec=ProviderRegistry)
    registry.list.return_value = ["anthropic", "ollama"]

    def _get(name: str | None = None) -> MagicMock:
        provider = MagicMock()
        provider.name = name or "anthropic"
        provider.default_model = "claude-sonnet-4-6" if name == "anthropic" else "llama3.2"
        provider.list_models = AsyncMock(
            return_value=["claude-sonnet-4-6", "claude-opus-4-6"]
            if name == "anthropic"
            else ["llama3.2"]
        )
        return provider

    registry.get.side_effect = _get
    return registry


# ---------------------------------------------------------------------------
# Shared HTTP client
# ---------------------------------------------------------------------------


@pytest.fixture
async def api_client(
    mock_workspace_service: MagicMock,
    mock_agent_service: MagicMock,
    mock_provider_registry: MagicMock,
) -> AsyncIterator[httpx.AsyncClient]:
    """AsyncClient wired to a minimal app with both routers and mocked services."""
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(workspaces.router)
    app.include_router(agents.router)
    app.include_router(providers.router)
    app.dependency_overrides[get_workspace_service] = lambda: mock_workspace_service
    app.dependency_overrides[get_agent_service] = lambda: mock_agent_service
    app.dependency_overrides[get_db_session] = lambda: None
    app.dependency_overrides[get_provider_registry] = lambda: mock_provider_registry
    app.dependency_overrides[get_current_user] = lambda: DEV_USER
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
