"""Functional tests for /workspaces endpoints."""

from __future__ import annotations

import httpx


async def test_list_workspaces_includes_default(http_client: httpx.AsyncClient) -> None:
    response = await http_client.get("/workspaces/")

    assert response.status_code == 200
    names = [ws["name"] for ws in response.json()]
    assert "default" in names


async def test_create_workspace_returns_201(http_client: httpx.AsyncClient) -> None:
    response = await http_client.post(
        "/workspaces/",
        json={"name": "test-ws", "description": "A test workspace"},
    )

    assert response.status_code == 201


async def test_create_workspace_response_shape(http_client: httpx.AsyncClient) -> None:
    response = await http_client.post(
        "/workspaces/",
        json={"name": "test-ws-shape", "description": "Shape test"},
    )

    body = response.json()
    assert "name" in body
    assert "description" in body
    assert "metadata" in body
    assert "agents" in body
    assert "tools" in body


async def test_get_default_workspace(http_client: httpx.AsyncClient) -> None:
    response = await http_client.get("/workspaces/default")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "default"
    assert len(body["agents"]) > 0


async def test_get_workspace_not_found(http_client: httpx.AsyncClient) -> None:
    response = await http_client.get("/workspaces/nonexistent")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


async def test_create_duplicate_workspace_returns_409(http_client: httpx.AsyncClient) -> None:
    await http_client.post(
        "/workspaces/",
        json={"name": "dupe-ws", "description": "First"},
    )
    response = await http_client.post(
        "/workspaces/",
        json={"name": "dupe-ws", "description": "Second"},
    )

    assert response.status_code == 409
    assert response.json()["error"] == "already_exists"


async def test_update_workspace(http_client: httpx.AsyncClient) -> None:
    await http_client.post(
        "/workspaces/",
        json={"name": "update-ws", "description": "Original"},
    )
    response = await http_client.patch(
        "/workspaces/update-ws",
        json={"description": "Updated"},
    )

    assert response.status_code == 200
    assert response.json()["description"] == "Updated"


async def test_delete_workspace(http_client: httpx.AsyncClient) -> None:
    await http_client.post(
        "/workspaces/",
        json={"name": "delete-ws", "description": "To be deleted"},
    )
    response = await http_client.delete("/workspaces/delete-ws")

    assert response.status_code == 204
