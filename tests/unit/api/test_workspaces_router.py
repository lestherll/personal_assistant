"""Unit tests for api/routers/workspaces.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx

from personal_assistant.services.exceptions import AlreadyExistsError, NotFoundError
from personal_assistant.services.views import WorkspaceChatView
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
    await api_client.post("/workspaces/", json={"name": "ws1", "description": "A workspace"})
    mock_workspace_service.create_workspace.assert_called_once()
    call_kwargs = mock_workspace_service.create_workspace.call_args.kwargs
    assert call_kwargs["name"] == "ws1"
    assert call_kwargs["description"] == "A workspace"
    assert call_kwargs["metadata"] == {}


async def test_create_workspace_already_exists_returns_409(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.create_workspace.side_effect = AlreadyExistsError("workspace", "ws1")
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
    mock_workspace_service.get_workspace.side_effect = NotFoundError("workspace", "missing")
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
    response = await api_client.patch("/workspaces/ws1", json={"description": "Updated"})
    assert response.status_code == 200


async def test_update_workspace_returns_updated_body(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.update_workspace.return_value = make_workspace_view(
        description="Updated"
    )
    response = await api_client.patch("/workspaces/ws1", json={"description": "Updated"})
    assert response.json()["description"] == "Updated"


async def test_update_workspace_not_found_returns_404(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.update_workspace.side_effect = NotFoundError("workspace", "missing")
    response = await api_client.patch("/workspaces/missing", json={"description": "x"})
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
    mock_workspace_service.delete_workspace.assert_called_once()
    call_args = mock_workspace_service.delete_workspace.call_args
    # user_id is first positional arg, workspace name is second
    assert call_args.args[1] == "ws1" or call_args.kwargs.get("name") == "ws1"


async def test_delete_workspace_not_found_returns_404(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.delete_workspace.side_effect = NotFoundError("workspace", "missing")
    response = await api_client.delete("/workspaces/missing")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /workspaces/{name}/chat — workspace chat
# ---------------------------------------------------------------------------


async def test_workspace_chat_returns_200(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.chat.return_value = WorkspaceChatView(
        response="ok", conversation_id="t1", agent_used="Bot"
    )
    response = await api_client.post("/workspaces/ws1/chat", json={"message": "hello"})
    assert response.status_code == 200


async def test_workspace_chat_returns_response_body(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.chat.return_value = WorkspaceChatView(
        response="ok", conversation_id="t1", agent_used="Bot"
    )
    response = await api_client.post("/workspaces/ws1/chat", json={"message": "hello"})
    data = response.json()
    assert data["response"] == "ok"
    assert data["conversation_id"] == "t1"
    assert data["agent_used"] == "Bot"


async def test_workspace_chat_calls_service(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    from api.dependencies import DEV_USER

    mock_workspace_service.chat.return_value = WorkspaceChatView(
        response="ok", conversation_id="t1", agent_used="Bot"
    )
    await api_client.post("/workspaces/ws1/chat", json={"message": "hello"})
    mock_workspace_service.chat.assert_awaited_once()
    call_args = mock_workspace_service.chat.call_args
    assert call_args.args[0] == DEV_USER.id
    call_kwargs = call_args.kwargs
    assert call_kwargs["workspace_name"] == "ws1"
    assert call_kwargs["message"] == "hello"


async def test_workspace_chat_not_found_returns_404(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.chat.side_effect = NotFoundError("workspace", "missing")
    response = await api_client.post("/workspaces/missing/chat", json={"message": "hello"})
    assert response.status_code == 404


async def test_workspace_chat_passes_conversation_id(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.chat.return_value = WorkspaceChatView(
        response="ok", conversation_id="my-thread", agent_used="Bot"
    )
    await api_client.post(
        "/workspaces/ws1/chat", json={"message": "hello", "conversation_id": "my-thread"}
    )
    call_kwargs = mock_workspace_service.chat.call_args.kwargs
    assert call_kwargs["conversation_id"] == "my-thread"


async def test_workspace_chat_passes_agent_name(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.chat.return_value = WorkspaceChatView(
        response="ok", conversation_id="t1", agent_used="Assistant"
    )
    await api_client.post(
        "/workspaces/ws1/chat", json={"message": "hello", "agent_name": "Assistant"}
    )
    call_kwargs = mock_workspace_service.chat.call_args.kwargs
    assert call_kwargs["agent_name"] == "Assistant"


async def test_workspace_chat_passes_provider_and_model(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    mock_workspace_service.chat.return_value = WorkspaceChatView(
        response="ok", conversation_id="t1", agent_used="Assistant"
    )
    await api_client.post(
        "/workspaces/ws1/chat",
        json={
            "message": "hello",
            "agent_name": "Assistant",
            "provider": "anthropic",
            "model": "claude-haiku-4-5-20251001",
        },
    )
    call_kwargs = mock_workspace_service.chat.call_args.kwargs
    assert call_kwargs["provider"] == "anthropic"
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"


async def test_workspace_chat_validation_error_returns_422(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    from personal_assistant.services.exceptions import ServiceValidationError

    mock_workspace_service.chat.side_effect = ServiceValidationError(
        "provider/model override requires agent_name"
    )
    response = await api_client.post(
        "/workspaces/ws1/chat", json={"message": "hello", "provider": "anthropic"}
    )
    assert response.status_code == 422


async def test_workspace_chat_stream_returns_streaming_response(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    async def fake_tokens():
        yield "Hello"
        yield " world"

    mock_workspace_service.stream_chat.return_value = (fake_tokens(), "conv-123", "Bot")
    response = await api_client.post(
        "/workspaces/ws1/chat/stream",
        json={"message": "hello", "agent_name": "Bot"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert response.headers["x-conversation-id"] == "conv-123"
    assert response.headers["x-agent-used"] == "Bot"


async def test_workspace_chat_stream_validation_error_returns_422(
    api_client: httpx.AsyncClient, mock_workspace_service: MagicMock
) -> None:
    from personal_assistant.services.exceptions import ServiceValidationError

    mock_workspace_service.stream_chat.side_effect = ServiceValidationError(
        "stream_chat requires agent_name"
    )
    response = await api_client.post("/workspaces/ws1/chat/stream", json={"message": "hello"})
    assert response.status_code == 422
