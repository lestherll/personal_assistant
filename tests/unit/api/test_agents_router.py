"""Unit tests for api/routers/agents.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from api.dependencies import get_agent_service
from api.exception_handlers import register_exception_handlers
from api.routers import agents
from personal_assistant.services.exceptions import AlreadyExistsError, NotFoundError
from personal_assistant.services.views import AgentConfigView, AgentView

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CREATE_BODY = {
    "name": "Assistant",
    "description": "General agent",
    "system_prompt": "You are helpful.",
}


def _agent_view(name: str = "Assistant") -> AgentView:
    return AgentView(
        config=AgentConfigView(
            name=name,
            description="General agent",
            system_prompt="You are helpful.",
            provider="ollama",
            model="qwen2.5:14b",
            allowed_tools=[],
        ),
        tools=[],
        llm_info={"provider": "ollama", "model": "qwen2.5:14b", "source": "registry"},
    )


@pytest.fixture
def mock_service() -> MagicMock:
    return MagicMock()


@pytest.fixture
def router_app(mock_service: MagicMock) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(agents.router)
    app.dependency_overrides[get_agent_service] = lambda: mock_service
    return app


# ---------------------------------------------------------------------------
# POST /workspaces/{workspace_name}/agents/ — create
# ---------------------------------------------------------------------------


async def test_create_agent_returns_201(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.create_agent.return_value = _agent_view()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.post("/workspaces/ws1/agents/", json=_CREATE_BODY)
    assert response.status_code == 201


async def test_create_agent_returns_body(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.create_agent.return_value = _agent_view()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.post("/workspaces/ws1/agents/", json=_CREATE_BODY)
    data = response.json()
    assert data["config"]["name"] == "Assistant"


async def test_create_agent_calls_service(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.create_agent.return_value = _agent_view()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        await client.post("/workspaces/ws1/agents/", json=_CREATE_BODY)
    mock_service.create_agent.assert_called_once_with(
        workspace_name="ws1",
        name="Assistant",
        description="General agent",
        system_prompt="You are helpful.",
        provider=None,
        model=None,
        allowed_tools=[],
    )


async def test_create_agent_workspace_not_found_returns_404(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.create_agent.side_effect = NotFoundError("workspace", "ws1")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.post("/workspaces/ws1/agents/", json=_CREATE_BODY)
    assert response.status_code == 404


async def test_create_agent_already_exists_returns_409(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.create_agent.side_effect = AlreadyExistsError("agent", "Assistant")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.post("/workspaces/ws1/agents/", json=_CREATE_BODY)
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# GET /workspaces/{workspace_name}/agents/ — list
# ---------------------------------------------------------------------------


async def test_list_agents_returns_200(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.list_agents.return_value = [_agent_view("A"), _agent_view("B")]
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.get("/workspaces/ws1/agents/")
    assert response.status_code == 200


async def test_list_agents_returns_all(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.list_agents.return_value = [_agent_view("A"), _agent_view("B")]
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.get("/workspaces/ws1/agents/")
    assert len(response.json()) == 2


async def test_list_agents_workspace_not_found_returns_404(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.list_agents.side_effect = NotFoundError("workspace", "missing")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.get("/workspaces/missing/agents/")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /workspaces/{workspace_name}/agents/{agent_name} — get
# ---------------------------------------------------------------------------


async def test_get_agent_returns_200(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.get_agent.return_value = _agent_view()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.get("/workspaces/ws1/agents/Assistant")
    assert response.status_code == 200


async def test_get_agent_returns_body(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.get_agent.return_value = _agent_view()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.get("/workspaces/ws1/agents/Assistant")
    assert response.json()["config"]["name"] == "Assistant"


async def test_get_agent_not_found_returns_404(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.get_agent.side_effect = NotFoundError("agent", "missing")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.get("/workspaces/ws1/agents/missing")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /workspaces/{workspace_name}/agents/{agent_name} — update
# ---------------------------------------------------------------------------


async def test_update_agent_returns_200(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.update_agent.return_value = _agent_view()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.patch(
            "/workspaces/ws1/agents/Assistant", json={"description": "Updated"}
        )
    assert response.status_code == 200


async def test_update_agent_calls_service(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.update_agent.return_value = _agent_view()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        await client.patch(
            "/workspaces/ws1/agents/Assistant", json={"description": "Updated"}
        )
    mock_service.update_agent.assert_called_once_with(
        "ws1",
        "Assistant",
        description="Updated",
        system_prompt=None,
        provider=None,
        model=None,
        allowed_tools=None,
    )


async def test_update_agent_not_found_returns_404(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.update_agent.side_effect = NotFoundError("agent", "missing")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.patch(
            "/workspaces/ws1/agents/missing", json={"description": "x"}
        )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /workspaces/{workspace_name}/agents/{agent_name}
# ---------------------------------------------------------------------------


async def test_delete_agent_returns_204(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.delete_agent.return_value = None
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.delete("/workspaces/ws1/agents/Assistant")
    assert response.status_code == 204


async def test_delete_agent_calls_service(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.delete_agent.return_value = None
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        await client.delete("/workspaces/ws1/agents/Assistant")
    mock_service.delete_agent.assert_called_once_with("ws1", "Assistant")


async def test_delete_agent_not_found_returns_404(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.delete_agent.side_effect = NotFoundError("agent", "missing")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.delete("/workspaces/ws1/agents/missing")
    assert response.status_code == 404
