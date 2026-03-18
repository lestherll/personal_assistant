"""Functional tests for /workspaces/{workspace_name}/agents endpoints."""

from __future__ import annotations

import uuid

import httpx

_CREATE_AGENT_BODY = {
    "name": "TestAgent",
    "description": "A test agent",
    "system_prompt": "You are a test agent.",
}


# ---------------------------------------------------------------------------
# Agent CRUD
# ---------------------------------------------------------------------------


async def test_list_agents_in_default_workspace(http_client: httpx.AsyncClient) -> None:
    response = await http_client.get("/workspaces/default/agents/")

    assert response.status_code == 200
    names = [a["config"]["name"] for a in response.json()]
    assert "Assistant" in names


async def test_list_agents_respects_limit(http_client: httpx.AsyncClient) -> None:
    response = await http_client.get("/workspaces/default/agents/?limit=1")

    assert response.status_code == 200
    assert len(response.json()) == 1


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


# ---------------------------------------------------------------------------
# Agent chat (non-streaming)
# ---------------------------------------------------------------------------


async def test_agent_chat_returns_200(http_client: httpx.AsyncClient) -> None:
    response = await http_client.post(
        "/workspaces/default/agents/Assistant/chat",
        json={"message": "Hello"},
    )

    assert response.status_code == 200


async def test_agent_chat_response_shape(http_client: httpx.AsyncClient) -> None:
    response = await http_client.post(
        "/workspaces/default/agents/Assistant/chat",
        json={"message": "Hello"},
    )

    body = response.json()
    assert "reply" in body
    assert "conversation_id" in body
    assert isinstance(body["reply"], str)
    assert isinstance(body["conversation_id"], str)


async def test_agent_chat_returns_mock_reply(http_client: httpx.AsyncClient) -> None:
    response = await http_client.post(
        "/workspaces/default/agents/Assistant/chat",
        json={"message": "Hello"},
    )

    assert "Assistant" in response.json()["reply"]


async def test_agent_chat_unknown_agent_returns_404(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    # Requires real service validation (run_agent not mocked)
    response = await http_client_realdb.post(
        "/workspaces/default/agents/GhostAgent/chat",
        json={"message": "Hello"},
    )

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


async def test_agent_chat_unknown_workspace_returns_404(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    # Requires real service validation (run_agent not mocked)
    response = await http_client_realdb.post(
        "/workspaces/nonexistent/agents/Assistant/chat",
        json={"message": "Hello"},
    )

    assert response.status_code == 404


async def test_agent_chat_preserves_conversation_id(http_client: httpx.AsyncClient) -> None:
    first = await http_client.post(
        "/workspaces/default/agents/Assistant/chat",
        json={"message": "My name is Alice."},
    )
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]
    assert conversation_id

    second = await http_client.post(
        "/workspaces/default/agents/Assistant/chat",
        json={"message": "What is my name?", "conversation_id": conversation_id},
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id


# ---------------------------------------------------------------------------
# Agent chat (streaming)
# ---------------------------------------------------------------------------


async def test_agent_chat_stream_returns_200(http_client: httpx.AsyncClient) -> None:
    async with http_client.stream(
        "POST",
        "/workspaces/default/agents/Assistant/chat/stream",
        json={"message": "Hello"},
    ) as resp:
        assert resp.status_code == 200
        async for _ in resp.aiter_bytes():
            pass


async def test_agent_chat_stream_has_conversation_id_header(
    http_client: httpx.AsyncClient,
) -> None:
    async with http_client.stream(
        "POST",
        "/workspaces/default/agents/Assistant/chat/stream",
        json={"message": "Hello"},
    ) as resp:
        body = b""
        async for chunk in resp.aiter_bytes():
            body += chunk

    assert resp.headers.get("x-conversation-id")


async def test_agent_chat_stream_sse_format(http_client: httpx.AsyncClient) -> None:
    async with http_client.stream(
        "POST",
        "/workspaces/default/agents/Assistant/chat/stream",
        json={"message": "Hello"},
    ) as resp:
        body = b""
        async for chunk in resp.aiter_bytes():
            body += chunk

    text = body.decode()
    assert "data:" in text
    assert "data: [DONE]" in text


async def test_agent_chat_stream_unknown_agent_returns_404(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    # Requires real service validation (stream_agent not mocked)
    response = await http_client_realdb.post(
        "/workspaces/default/agents/GhostAgent/chat/stream",
        json={"message": "Hello"},
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Conversation list (Tier 1 — no DB state required)
# ---------------------------------------------------------------------------


async def test_list_agent_conversations_returns_200(http_client: httpx.AsyncClient) -> None:
    response = await http_client.get("/workspaces/default/agents/Assistant/conversations")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_list_agent_conversations_unknown_workspace_returns_404(
    http_client: httpx.AsyncClient,
) -> None:
    response = await http_client.get("/workspaces/nonexistent/agents/Assistant/conversations")

    assert response.status_code == 404


async def test_delete_nonexistent_conversation_returns_404(
    http_client: httpx.AsyncClient,
) -> None:
    random_id = str(uuid.uuid4())
    response = await http_client.delete(
        f"/workspaces/default/agents/Assistant/conversations/{random_id}"
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Conversation list + delete (Tier 2 — real DB writes)
# ---------------------------------------------------------------------------


async def test_list_agent_conversations_after_chat(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    await http_client_realdb.post(
        "/workspaces/default/agents/Assistant/chat",
        json={"message": "Hello, record me."},
    )
    response = await http_client_realdb.get("/workspaces/default/agents/Assistant/conversations")

    assert response.status_code == 200
    assert len(response.json()) >= 1


async def test_list_agent_conversations_response_has_workspace_id(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    await http_client_realdb.post(
        "/workspaces/default/agents/Assistant/chat",
        json={"message": "Check my fields."},
    )
    response = await http_client_realdb.get("/workspaces/default/agents/Assistant/conversations")

    assert response.status_code == 200
    convs = response.json()
    assert len(convs) >= 1
    first = convs[0]
    assert "id" in first
    assert "workspace_id" in first
    # workspace_id must be a valid UUID string — not a workspace name
    uuid.UUID(first["workspace_id"])


async def test_list_agent_conversations_respects_limit(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    await http_client_realdb.post(
        "/workspaces/default/agents/Assistant/chat",
        json={"message": "Pagination convo 1"},
    )
    await http_client_realdb.post(
        "/workspaces/default/agents/Assistant/chat",
        json={"message": "Pagination convo 2"},
    )
    response = await http_client_realdb.get(
        "/workspaces/default/agents/Assistant/conversations?limit=1"
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_delete_conversation_returns_204(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    chat = await http_client_realdb.post(
        "/workspaces/default/agents/Assistant/chat",
        json={"message": "Delete me."},
    )
    conversation_id = chat.json()["conversation_id"]

    response = await http_client_realdb.delete(
        f"/workspaces/default/agents/Assistant/conversations/{conversation_id}"
    )

    assert response.status_code == 204


async def test_delete_conversation_then_list_excludes_it(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    chat = await http_client_realdb.post(
        "/workspaces/default/agents/Assistant/chat",
        json={"message": "Soon to be gone."},
    )
    conversation_id = chat.json()["conversation_id"]

    await http_client_realdb.delete(
        f"/workspaces/default/agents/Assistant/conversations/{conversation_id}"
    )

    response = await http_client_realdb.get("/workspaces/default/agents/Assistant/conversations")
    ids = [c["id"] for c in response.json()]
    assert conversation_id not in ids
