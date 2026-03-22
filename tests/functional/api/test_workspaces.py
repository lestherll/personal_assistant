"""Functional tests for /workspaces endpoints."""

from __future__ import annotations

import uuid

import httpx

# ---------------------------------------------------------------------------
# Workspace CRUD
# ---------------------------------------------------------------------------


async def test_list_workspaces_includes_default(http_client: httpx.AsyncClient) -> None:
    response = await http_client.get("/workspaces/")

    assert response.status_code == 200
    names = [ws["name"] for ws in response.json()]
    assert "default" in names


async def test_list_workspaces_respects_limit(http_client: httpx.AsyncClient) -> None:
    response = await http_client.get("/workspaces/?limit=1")

    assert response.status_code == 200
    assert len(response.json()) == 1


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


# ---------------------------------------------------------------------------
# Workspace chat (non-streaming)
# ---------------------------------------------------------------------------


async def test_workspace_chat_returns_response_shape(http_client: httpx.AsyncClient) -> None:
    response = await http_client.post(
        "/workspaces/default/chat",
        json={"message": "Say 'hello' and nothing else."},
        timeout=120.0,
    )

    assert response.status_code == 200
    body = response.json()
    assert "response" in body
    assert "conversation_id" in body
    assert "agent_used" in body
    assert isinstance(body["response"], str)
    assert len(body["response"]) > 0


async def test_workspace_chat_preserves_conversation_id(http_client: httpx.AsyncClient) -> None:
    first = await http_client.post(
        "/workspaces/default/chat",
        json={"message": "My name is Alice."},
        timeout=120.0,
    )
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]
    assert conversation_id

    second = await http_client.post(
        "/workspaces/default/chat",
        json={"message": "What is my name?", "conversation_id": conversation_id},
        timeout=120.0,
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id


async def test_workspace_chat_not_found(http_client: httpx.AsyncClient) -> None:
    response = await http_client.post(
        "/workspaces/nonexistent/chat",
        json={"message": "Hello"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Workspace chat (streaming)
# ---------------------------------------------------------------------------


async def test_workspace_chat_stream_returns_200(http_client: httpx.AsyncClient) -> None:
    async with http_client.stream(
        "POST",
        "/workspaces/default/chat/stream",
        json={"message": "Hello", "agent_name": "Assistant"},
    ) as resp:
        assert resp.status_code == 200
        async for _ in resp.aiter_bytes():
            pass


async def test_workspace_chat_stream_has_headers(http_client: httpx.AsyncClient) -> None:
    async with http_client.stream(
        "POST",
        "/workspaces/default/chat/stream",
        json={"message": "Hello", "agent_name": "Assistant"},
    ) as resp:
        body = b""
        async for chunk in resp.aiter_bytes():
            body += chunk

    assert resp.headers.get("x-conversation-id")
    assert resp.headers.get("x-agent-used")


async def test_workspace_chat_stream_sse_format(http_client: httpx.AsyncClient) -> None:
    async with http_client.stream(
        "POST",
        "/workspaces/default/chat/stream",
        json={"message": "Hello", "agent_name": "Assistant"},
    ) as resp:
        body = b""
        async for chunk in resp.aiter_bytes():
            body += chunk

    text = body.decode()
    assert "data:" in text
    assert "data: [DONE]" in text


async def test_workspace_chat_stream_unknown_workspace_returns_404(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    # Requires real service validation (stream_agent not mocked)
    response = await http_client_realdb.post(
        "/workspaces/nonexistent/chat/stream",
        json={"message": "Hello", "agent_name": "Assistant"},
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Conversation list (Tier 1 — no DB state required)
# ---------------------------------------------------------------------------


async def test_list_conversations_returns_200(http_client: httpx.AsyncClient) -> None:
    response = await http_client.get("/workspaces/default/conversations")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_list_conversations_unknown_workspace_returns_404(
    http_client: httpx.AsyncClient,
) -> None:
    response = await http_client.get("/workspaces/nonexistent/conversations")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Conversation list (Tier 2 — real DB writes)
# ---------------------------------------------------------------------------


async def test_list_conversations_after_chat_has_entry(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    await http_client_realdb.post(
        "/workspaces/default/chat",
        json={"message": "Record this.", "agent_name": "Assistant"},
    )
    response = await http_client_realdb.get("/workspaces/default/conversations")

    assert response.status_code == 200
    assert len(response.json()) >= 1


async def test_list_conversations_response_shape(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    await http_client_realdb.post(
        "/workspaces/default/chat",
        json={"message": "Check fields.", "agent_name": "Assistant"},
    )
    response = await http_client_realdb.get("/workspaces/default/conversations")

    assert response.status_code == 200
    convs = response.json()
    assert len(convs) >= 1
    first = convs[0]
    # Verify the new schema: workspace_id is a UUID, not workspace_name string
    assert "id" in first
    assert "workspace_id" in first
    assert "created_at" in first
    assert "updated_at" in first
    assert "workspace_name" not in first
    uuid.UUID(first["workspace_id"])


async def test_list_conversations_respects_limit(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    await http_client_realdb.post(
        "/workspaces/default/chat",
        json={"message": "Pagination message 1", "agent_name": "Assistant"},
    )
    await http_client_realdb.post(
        "/workspaces/default/chat",
        json={"message": "Pagination message 2", "agent_name": "Assistant"},
    )

    response = await http_client_realdb.get("/workspaces/default/conversations?limit=1")
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_rename_conversation_updates_title(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    chat = await http_client_realdb.post(
        "/workspaces/default/chat",
        json={"message": "Please rename this chat.", "agent_name": "Assistant"},
    )
    assert chat.status_code == 200
    conversation_id = chat.json()["conversation_id"]

    rename = await http_client_realdb.patch(
        f"/workspaces/default/conversations/{conversation_id}",
        json={"title": "Renamed Conversation"},
    )
    assert rename.status_code == 204

    listed = await http_client_realdb.get("/workspaces/default/conversations")
    assert listed.status_code == 200
    conv = next((c for c in listed.json() if c["id"] == conversation_id), None)
    assert conv is not None
    assert conv["title"] == "Renamed Conversation"


# ---------------------------------------------------------------------------
# Agent participation (Tier 1 — error cases)
# ---------------------------------------------------------------------------


async def test_agent_participation_unknown_workspace_returns_404(
    http_client: httpx.AsyncClient,
) -> None:
    random_id = str(uuid.uuid4())
    response = await http_client.get(f"/workspaces/nonexistent/conversations/{random_id}/agents")

    assert response.status_code == 404


async def test_agent_participation_unknown_conversation_returns_404(
    http_client: httpx.AsyncClient,
) -> None:
    random_id = str(uuid.uuid4())
    response = await http_client.get(f"/workspaces/default/conversations/{random_id}/agents")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Agent participation (Tier 2 — real DB writes)
# ---------------------------------------------------------------------------


async def test_agent_participation_after_chat_returns_list(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    chat = await http_client_realdb.post(
        "/workspaces/default/chat",
        json={"message": "Who contributed?", "agent_name": "Assistant"},
    )
    assert chat.status_code == 200
    conversation_id = chat.json()["conversation_id"]

    response = await http_client_realdb.get(
        f"/workspaces/default/conversations/{conversation_id}/agents"
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_agent_participation_response_shape(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    chat = await http_client_realdb.post(
        "/workspaces/default/chat",
        json={"message": "Track my agent.", "agent_name": "Assistant"},
    )
    conversation_id = chat.json()["conversation_id"]

    response = await http_client_realdb.get(
        f"/workspaces/default/conversations/{conversation_id}/agents"
    )

    assert response.status_code == 200
    participants = response.json()
    assert len(participants) >= 1
    first = participants[0]
    assert "agent_id" in first
    assert "agent_name" in first
    assert "message_count" in first
    assert first["message_count"] >= 1


# ---------------------------------------------------------------------------
# DELETE /workspaces/{name}/conversations/{id}
# ---------------------------------------------------------------------------


async def test_delete_conversation_unknown_workspace_returns_404(
    http_client: httpx.AsyncClient,
) -> None:
    random_id = str(uuid.uuid4())
    response = await http_client.delete(f"/workspaces/nonexistent/conversations/{random_id}")

    assert response.status_code == 404


async def test_delete_conversation_unknown_conversation_returns_404(
    http_client: httpx.AsyncClient,
) -> None:
    random_id = str(uuid.uuid4())
    response = await http_client.delete(f"/workspaces/default/conversations/{random_id}")

    assert response.status_code == 404


async def test_delete_conversation_removes_it_from_list(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    chat = await http_client_realdb.post(
        "/workspaces/default/chat",
        json={"message": "Delete me.", "agent_name": "Assistant"},
    )
    assert chat.status_code == 200
    conversation_id = chat.json()["conversation_id"]

    delete = await http_client_realdb.delete(f"/workspaces/default/conversations/{conversation_id}")
    assert delete.status_code == 204

    listed = await http_client_realdb.get("/workspaces/default/conversations")
    assert listed.status_code == 200
    ids = [c["id"] for c in listed.json()]
    assert conversation_id not in ids


async def test_delete_conversation_returns_404_on_second_delete(
    http_client_realdb: httpx.AsyncClient,
) -> None:
    chat = await http_client_realdb.post(
        "/workspaces/default/chat",
        json={"message": "Delete me twice.", "agent_name": "Assistant"},
    )
    conversation_id = chat.json()["conversation_id"]

    await http_client_realdb.delete(f"/workspaces/default/conversations/{conversation_id}")
    second = await http_client_realdb.delete(f"/workspaces/default/conversations/{conversation_id}")
    assert second.status_code == 404
