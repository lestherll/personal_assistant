"""Functional tests for /workspaces/{workspace_name}/agents endpoints."""

from __future__ import annotations

import httpx

_CREATE_AGENT_BODY = {
    "name": "TestAgent",
    "description": "A test agent",
    "system_prompt": "You are a test agent.",
}


async def test_list_agents_in_default_workspace(http_client: httpx.AsyncClient) -> None:
    response = await http_client.get("/workspaces/default/agents/")

    assert response.status_code == 200
    names = [a["config"]["name"] for a in response.json()]
    assert "Assistant" in names


async def test_get_agent(http_client: httpx.AsyncClient) -> None:
    response = await http_client.get("/workspaces/default/agents/Assistant")

    assert response.status_code == 200
    body = response.json()
    assert body["config"]["name"] == "Assistant"
    assert "tools" in body
    assert "llm_info" in body


async def test_get_agent_not_found(http_client: httpx.AsyncClient) -> None:
    response = await http_client.get("/workspaces/default/agents/nonexistent")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


async def test_list_agents_workspace_not_found(http_client: httpx.AsyncClient) -> None:
    response = await http_client.get("/workspaces/nonexistent/agents/")

    assert response.status_code == 404


async def test_create_agent(http_client: httpx.AsyncClient) -> None:
    response = await http_client.post("/workspaces/default/agents/", json=_CREATE_AGENT_BODY)

    assert response.status_code == 201


async def test_create_agent_response_shape(http_client: httpx.AsyncClient) -> None:
    response = await http_client.post(
        "/workspaces/default/agents/",
        json={**_CREATE_AGENT_BODY, "name": "ShapeAgent"},
    )

    body = response.json()
    assert "config" in body
    assert "tools" in body
    assert "llm_info" in body


async def test_create_duplicate_agent_returns_409(http_client: httpx.AsyncClient) -> None:
    await http_client.post(
        "/workspaces/default/agents/",
        json={**_CREATE_AGENT_BODY, "name": "DupeAgent"},
    )
    response = await http_client.post(
        "/workspaces/default/agents/",
        json={**_CREATE_AGENT_BODY, "name": "DupeAgent"},
    )

    assert response.status_code == 409
    assert response.json()["error"] == "already_exists"


async def test_update_agent(http_client: httpx.AsyncClient) -> None:
    await http_client.post(
        "/workspaces/default/agents/",
        json={**_CREATE_AGENT_BODY, "name": "UpdateAgent"},
    )
    response = await http_client.patch(
        "/workspaces/default/agents/UpdateAgent",
        json={"description": "Updated"},
    )

    assert response.status_code == 200
    assert response.json()["config"]["description"] == "Updated"


async def test_delete_agent(http_client: httpx.AsyncClient) -> None:
    await http_client.post(
        "/workspaces/default/agents/",
        json={**_CREATE_AGENT_BODY, "name": "DeleteAgent"},
    )
    response = await http_client.delete("/workspaces/default/agents/DeleteAgent")

    assert response.status_code == 204


async def test_reset_agent(http_client: httpx.AsyncClient) -> None:
    # The reset endpoint has been removed; expect 404 or 405.
    response = await http_client.post("/workspaces/default/agents/Assistant/reset")

    assert response.status_code in (404, 405)
