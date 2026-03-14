"""Shared fixtures for api unit tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from api.dependencies import get_agent_service, get_db_session, get_workspace_service
from api.exception_handlers import register_exception_handlers
from api.routers import agents, workspaces
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
    return MagicMock()


@pytest.fixture
def mock_agent_service() -> MagicMock:
    svc = MagicMock()
    svc.run_agent = AsyncMock()
    svc.stream_agent = AsyncMock()
    return svc


# ---------------------------------------------------------------------------
# Shared HTTP client
# ---------------------------------------------------------------------------


@pytest.fixture
async def api_client(
    mock_workspace_service: MagicMock,
    mock_agent_service: MagicMock,
) -> AsyncIterator[httpx.AsyncClient]:
    """AsyncClient wired to a minimal app with both routers and mocked services."""
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(workspaces.router)
    app.include_router(agents.router)
    app.dependency_overrides[get_workspace_service] = lambda: mock_workspace_service
    app.dependency_overrides[get_agent_service] = lambda: mock_agent_service
    app.dependency_overrides[get_db_session] = lambda: None
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
