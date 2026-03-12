"""Unit tests for api/routers/workspaces.py.

Each test wires a minimal FastAPI app with the workspaces router and a mocked
WorkspaceService, then drives it via httpx.AsyncClient with ASGITransport.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from api.dependencies import get_workspace_service
from api.exception_handlers import register_exception_handlers
from api.routers import workspaces
from personal_assistant.services.exceptions import AlreadyExistsError, NotFoundError
from personal_assistant.services.views import (
    AgentConfigView,
    AgentView,
    WorkspaceDetailView,
    WorkspaceView,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ws_view(name: str = "ws1", **kwargs: Any) -> WorkspaceView:
    defaults: dict[str, Any] = {
        "name": name,
        "description": "A workspace",
        "metadata": {},
        "agents": [],
        "tools": [],
    }
    defaults.update(kwargs)
    return WorkspaceView(**defaults)


def _agent_view(agent_name: str = "TestAgent") -> AgentView:
    return AgentView(
        config=AgentConfigView(
            name=agent_name,
            description="desc",
            system_prompt="You are helpful.",
            provider="ollama",
            model="qwen2.5:14b",
            allowed_tools=[],
        ),
        tools=[],
        llm_info={"provider": "ollama", "model": "qwen2.5:14b", "source": "registry"},
    )


def _ws_detail_view(name: str = "ws1") -> WorkspaceDetailView:
    return WorkspaceDetailView(
        name=name,
        description="A workspace",
        metadata={},
        agents=[_agent_view()],
        tools=[],
    )


@pytest.fixture
def mock_service() -> MagicMock:
    return MagicMock()


@pytest.fixture
def router_app(mock_service: MagicMock) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(workspaces.router)
    app.dependency_overrides[get_workspace_service] = lambda: mock_service
    return app


# ---------------------------------------------------------------------------
# POST /workspaces/ — create
# ---------------------------------------------------------------------------


async def test_create_workspace_returns_201(router_app: FastAPI, mock_service: MagicMock) -> None:
    mock_service.create_workspace.return_value = _ws_view()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/workspaces/", json={"name": "ws1", "description": "A workspace"}
        )
    assert response.status_code == 201


async def test_create_workspace_returns_body(router_app: FastAPI, mock_service: MagicMock) -> None:
    mock_service.create_workspace.return_value = _ws_view()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/workspaces/", json={"name": "ws1", "description": "A workspace"}
        )
    data = response.json()
    assert data["name"] == "ws1"
    assert data["description"] == "A workspace"


async def test_create_workspace_calls_service(router_app: FastAPI, mock_service: MagicMock) -> None:
    mock_service.create_workspace.return_value = _ws_view()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        await client.post("/workspaces/", json={"name": "ws1", "description": "A workspace"})
    mock_service.create_workspace.assert_called_once_with(
        name="ws1", description="A workspace", metadata={}
    )


async def test_create_workspace_already_exists_returns_409(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.create_workspace.side_effect = AlreadyExistsError("workspace", "ws1")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/workspaces/", json={"name": "ws1", "description": "A workspace"}
        )
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# GET /workspaces/ — list
# ---------------------------------------------------------------------------


async def test_list_workspaces_returns_200(router_app: FastAPI, mock_service: MagicMock) -> None:
    mock_service.list_workspaces.return_value = [_ws_view("ws1"), _ws_view("ws2")]
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.get("/workspaces/")
    assert response.status_code == 200


async def test_list_workspaces_returns_all(router_app: FastAPI, mock_service: MagicMock) -> None:
    mock_service.list_workspaces.return_value = [_ws_view("ws1"), _ws_view("ws2")]
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.get("/workspaces/")
    assert len(response.json()) == 2


async def test_list_workspaces_empty(router_app: FastAPI, mock_service: MagicMock) -> None:
    mock_service.list_workspaces.return_value = []
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.get("/workspaces/")
    assert response.json() == []


# ---------------------------------------------------------------------------
# GET /workspaces/{name} — detail
# ---------------------------------------------------------------------------


async def test_get_workspace_returns_200(router_app: FastAPI, mock_service: MagicMock) -> None:
    mock_service.get_workspace.return_value = _ws_detail_view()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.get("/workspaces/ws1")
    assert response.status_code == 200


async def test_get_workspace_detail_includes_agents(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.get_workspace.return_value = _ws_detail_view()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.get("/workspaces/ws1")
    data = response.json()
    assert len(data["agents"]) == 1
    assert data["agents"][0]["config"]["name"] == "TestAgent"


async def test_get_workspace_not_found_returns_404(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.get_workspace.side_effect = NotFoundError("workspace", "missing")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.get("/workspaces/missing")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /workspaces/{name} — update
# ---------------------------------------------------------------------------


async def test_update_workspace_returns_200(router_app: FastAPI, mock_service: MagicMock) -> None:
    mock_service.update_workspace.return_value = _ws_view(description="Updated")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.patch("/workspaces/ws1", json={"description": "Updated"})
    assert response.status_code == 200


async def test_update_workspace_returns_updated_body(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.update_workspace.return_value = _ws_view(description="Updated")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.patch("/workspaces/ws1", json={"description": "Updated"})
    assert response.json()["description"] == "Updated"


async def test_update_workspace_not_found_returns_404(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.update_workspace.side_effect = NotFoundError("workspace", "missing")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.patch("/workspaces/missing", json={"description": "x"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /workspaces/{name}
# ---------------------------------------------------------------------------


async def test_delete_workspace_returns_204(router_app: FastAPI, mock_service: MagicMock) -> None:
    mock_service.delete_workspace.return_value = None
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.delete("/workspaces/ws1")
    assert response.status_code == 204


async def test_delete_workspace_calls_service(router_app: FastAPI, mock_service: MagicMock) -> None:
    mock_service.delete_workspace.return_value = None
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        await client.delete("/workspaces/ws1")
    mock_service.delete_workspace.assert_called_once_with("ws1")


async def test_delete_workspace_not_found_returns_404(
    router_app: FastAPI, mock_service: MagicMock
) -> None:
    mock_service.delete_workspace.side_effect = NotFoundError("workspace", "missing")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=router_app), base_url="http://test"
    ) as client:
        response = await client.delete("/workspaces/missing")
    assert response.status_code == 404
