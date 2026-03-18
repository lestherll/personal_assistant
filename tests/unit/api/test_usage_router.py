"""Unit tests for api/routers/usage.py."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from api.dependencies import DEV_USER, get_current_user, get_db_session, get_usage_service
from api.exception_handlers import register_exception_handlers
from api.routers import usage
from personal_assistant.services.views import UsageByAgentView, UsageSummaryView


@pytest.fixture
def mock_usage_service() -> MagicMock:
    svc = MagicMock()
    svc.get_usage_summary = AsyncMock(return_value=[])
    svc.get_usage_by_agent = AsyncMock(return_value=[])
    return svc


@pytest.fixture
async def usage_client(mock_usage_service: MagicMock) -> httpx.AsyncClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(usage.router)
    app.dependency_overrides[get_usage_service] = lambda: mock_usage_service
    app.dependency_overrides[get_db_session] = lambda: MagicMock()
    app.dependency_overrides[get_current_user] = lambda: DEV_USER

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


async def test_usage_summary_returns_items(
    usage_client: httpx.AsyncClient, mock_usage_service: MagicMock
) -> None:
    now = datetime(2026, 3, 1, tzinfo=UTC)
    mock_usage_service.get_usage_summary.return_value = [
        UsageSummaryView(
            workspace="default",
            provider="ollama",
            model="llama3.2",
            period_start=now,
            prompt_tokens=120,
            completion_tokens=80,
            total_tokens=200,
            estimated_cost_usd=0.0,
        )
    ]

    response = await usage_client.get("/usage/summary")
    assert response.status_code == 200
    data = response.json()
    assert data[0]["workspace"] == "default"
    assert data[0]["total_tokens"] == 200


async def test_usage_summary_passes_filters(
    usage_client: httpx.AsyncClient, mock_usage_service: MagicMock
) -> None:
    response = await usage_client.get(
        "/usage/summary",
        params={
            "workspace": "ws1",
            "provider": "ollama",
            "model": "llama3.2",
            "period": "week",
            "start": "2026-03-01T00:00:00Z",
            "end": "2026-03-08T00:00:00Z",
        },
    )
    assert response.status_code == 200
    call_kwargs = mock_usage_service.get_usage_summary.await_args.kwargs
    assert call_kwargs["workspace_name"] == "ws1"
    assert call_kwargs["provider"] == "ollama"
    assert call_kwargs["model"] == "llama3.2"
    assert call_kwargs["period"] == "week"
    assert isinstance(call_kwargs["start"], datetime)
    assert isinstance(call_kwargs["end"], datetime)


async def test_usage_by_agent_returns_items(
    usage_client: httpx.AsyncClient, mock_usage_service: MagicMock
) -> None:
    now = datetime(2026, 3, 2, tzinfo=UTC)
    agent_id = uuid.UUID("9a1c2f57-7b62-4f4d-8c3a-2d4a7f1f9d9d")
    mock_usage_service.get_usage_by_agent.return_value = [
        UsageByAgentView(
            workspace="default",
            agent_id=agent_id,
            agent_name="Assistant",
            provider="ollama",
            model="llama3.2",
            period_start=now,
            prompt_tokens=50,
            completion_tokens=25,
            total_tokens=75,
            estimated_cost_usd=0.0,
        )
    ]

    response = await usage_client.get("/usage/by-agent")
    assert response.status_code == 200
    data = response.json()
    assert data[0]["agent_name"] == "Assistant"
    assert data[0]["total_tokens"] == 75


async def test_usage_by_agent_passes_filters(
    usage_client: httpx.AsyncClient, mock_usage_service: MagicMock
) -> None:
    response = await usage_client.get(
        "/usage/by-agent",
        params={
            "workspace": "ws1",
            "agent": "Assistant",
            "provider": "ollama",
            "model": "llama3.2",
            "period": "month",
        },
    )
    assert response.status_code == 200
    call_kwargs = mock_usage_service.get_usage_by_agent.await_args.kwargs
    assert call_kwargs["workspace_name"] == "ws1"
    assert call_kwargs["agent_name"] == "Assistant"
    assert call_kwargs["provider"] == "ollama"
    assert call_kwargs["model"] == "llama3.2"
    assert call_kwargs["period"] == "month"
