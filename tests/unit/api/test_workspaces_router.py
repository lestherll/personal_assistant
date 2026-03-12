"""Unit tests for api/routers/workspaces.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from personal_assistant.services.exceptions import AlreadyExistsError, NotFoundError

from tests.unit.api.conftest import (
    make_workspace_detail_view,
    make_workspace_view,
)


# ---------------------------------------------------------------------------
# POST /workspaces/ — create
# ---------------------------------------------------------------------------


async def test_create_workspace_returns_201(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.create_workspace.return_value = make_workspace_view()
    response = await api_client.post(
        "/workspaces/", json={"name": "ws1", "description": "A workspace"}
    )
    assert response.status_code == 201


async def test_create_workspace_returns_body(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.create_workspace.return_value = make_workspace_view()
    response = await api_client.post(
        "/workspaces/", json={"name": "ws1", "description": "A workspace"}
    )
    data = response.json()
    assert data["name"] == "ws1"
    assert data["description"] == "A workspace"


async def test_create_workspace_calls_service(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.create_workspace.return_value = make_workspace_view()
    await api_client.post(
        "/workspaces/", json={"name": "ws1", "description": "A workspace"}
    )
    mock_workspace_service.create_workspace.assert_called_once_with(
        name="ws1", description="A workspace", metadata={}
    )


async def test_create_workspace_already_exists_returns_409(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.create_workspace.side_effect = AlreadyExistsError(
        "workspace", "ws1"
    )
    response = await api_client.post(
        "/workspaces/", json={"name": "ws1", "description": "A workspace"}
    )
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# GET /workspaces/ — list
# ---------------------------------------------------------------------------


async def test_list_workspaces_returns_200(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.list_workspaces.return_value = [
        make_workspace_view("ws1"),
        make_workspace_view("ws2"),
    ]
    response = await api_client.get("/workspaces/")
    assert response.status_code == 200


async def test_list_workspaces_returns_all(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.list_workspaces.return_value = [
        make_workspace_view("ws1"),
        make_workspace_view("ws2"),
    ]
    response = await api_client.get("/workspaces/")
    assert len(response.json()) == 2


async def test_list_workspaces_empty(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.list_workspaces.return_value = []
    response = await api_client.get("/workspaces/")
    assert response.json() == []


# ---------------------------------------------------------------------------
# GET /workspaces/{name} — detail
# ---------------------------------------------------------------------------


async def test_get_workspace_returns_200(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.get_workspace.return_value = make_workspace_detail_view()
    response = await api_client.get("/workspaces/ws1")
    assert response.status_code == 200


async def test_get_workspace_detail_includes_agents(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.get_workspace.return_value = make_workspace_detail_view()
    response = await api_client.get("/workspaces/ws1")
    data = response.json()
    assert len(data["agents"]) == 1
    assert data["agents"][0]["config"]["name"] == "Assistant"


async def test_get_workspace_not_found_returns_404(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.get_workspace.side_effect = NotFoundError(
        "workspace", "missing"
    )
    response = await api_client.get("/workspaces/missing")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /workspaces/{name} — update
# ---------------------------------------------------------------------------


async def test_update_workspace_returns_200(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.update_workspace.return_value = make_workspace_view(
        description="Updated"
    )
    response = await api_client.patch(
        "/workspaces/ws1", json={"description": "Updated"}
    )
    assert response.status_code == 200


async def test_update_workspace_returns_updated_body(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.update_workspace.return_value = make_workspace_view(
        description="Updated"
    )
    response = await api_client.patch(
        "/workspaces/ws1", json={"description": "Updated"}
    )
    assert response.json()["description"] == "Updated"


async def test_update_workspace_not_found_returns_404(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.update_workspace.side_effect = NotFoundError(
        "workspace", "missing"
    )
    response = await api_client.patch(
        "/workspaces/missing", json={"description": "x"}
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /workspaces/{name}
# ---------------------------------------------------------------------------


async def test_delete_workspace_returns_204(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.delete_workspace.return_value = None
    response = await api_client.delete("/workspaces/ws1")
    assert response.status_code == 204


async def test_delete_workspace_calls_service(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.delete_workspace.return_value = None
    await api_client.delete("/workspaces/ws1")
    mock_workspace_service.delete_workspace.assert_called_once_with("ws1")


async def test_delete_workspace_not_found_returns_404(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.delete_workspace.side_effect = NotFoundError(
        "workspace", "missing"
    )
    response = await api_client.delete("/workspaces/missing")
    assert response.status_code == 404
