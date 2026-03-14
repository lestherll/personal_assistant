"""Unit tests for api/routers/agents.py."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import httpx

from personal_assistant.services.exceptions import AlreadyExistsError, NotFoundError
from tests.unit.api.conftest import make_agent_view

_CREATE_BODY = {
    "name": "Assistant",
    "description": "General agent",
    "system_prompt": "You are helpful.",
}

_FIXED_UUID = uuid.uuid4()


# ---------------------------------------------------------------------------
# POST /workspaces/{workspace_name}/agents/ — create
# ---------------------------------------------------------------------------


async def test_create_agent_returns_201(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.create_agent.return_value = make_agent_view()
    response = await api_client.post("/workspaces/ws1/agents/", json=_CREATE_BODY)
    assert response.status_code == 201


async def test_create_agent_returns_body(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.create_agent.return_value = make_agent_view()
    response = await api_client.post("/workspaces/ws1/agents/", json=_CREATE_BODY)
    assert response.json()["config"]["name"] == "Assistant"


async def test_create_agent_calls_service(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.create_agent.return_value = make_agent_view()
    await api_client.post("/workspaces/ws1/agents/", json=_CREATE_BODY)
    mock_agent_service.create_agent.assert_called_once_with(
        workspace_name="ws1",
        name="Assistant",
        description="General agent",
        system_prompt="You are helpful.",
        provider=None,
        model=None,
        allowed_tools=[],
    )


async def test_create_agent_workspace_not_found_returns_404(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.create_agent.side_effect = NotFoundError("workspace", "ws1")
    response = await api_client.post("/workspaces/ws1/agents/", json=_CREATE_BODY)
    assert response.status_code == 404


async def test_create_agent_already_exists_returns_409(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.create_agent.side_effect = AlreadyExistsError("agent", "Assistant")
    response = await api_client.post("/workspaces/ws1/agents/", json=_CREATE_BODY)
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# GET /workspaces/{workspace_name}/agents/ — list
# ---------------------------------------------------------------------------


async def test_list_agents_returns_200(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.list_agents.return_value = [
        make_agent_view("A"),
        make_agent_view("B"),
    ]
    response = await api_client.get("/workspaces/ws1/agents/")
    assert response.status_code == 200


async def test_list_agents_returns_all(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.list_agents.return_value = [
        make_agent_view("A"),
        make_agent_view("B"),
    ]
    response = await api_client.get("/workspaces/ws1/agents/")
    assert len(response.json()) == 2


async def test_list_agents_workspace_not_found_returns_404(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.list_agents.side_effect = NotFoundError("workspace", "missing")
    response = await api_client.get("/workspaces/missing/agents/")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /workspaces/{workspace_name}/agents/{agent_name} — get
# ---------------------------------------------------------------------------


async def test_get_agent_returns_200(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.get_agent.return_value = make_agent_view()
    response = await api_client.get("/workspaces/ws1/agents/Assistant")
    assert response.status_code == 200


async def test_get_agent_returns_body(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.get_agent.return_value = make_agent_view()
    response = await api_client.get("/workspaces/ws1/agents/Assistant")
    assert response.json()["config"]["name"] == "Assistant"


async def test_get_agent_not_found_returns_404(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.get_agent.side_effect = NotFoundError("agent", "missing")
    response = await api_client.get("/workspaces/ws1/agents/missing")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /workspaces/{workspace_name}/agents/{agent_name} — update
# ---------------------------------------------------------------------------


async def test_update_agent_returns_200(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.update_agent.return_value = make_agent_view()
    response = await api_client.patch(
        "/workspaces/ws1/agents/Assistant", json={"description": "Updated"}
    )
    assert response.status_code == 200


async def test_update_agent_calls_service(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.update_agent.return_value = make_agent_view()
    await api_client.patch("/workspaces/ws1/agents/Assistant", json={"description": "Updated"})
    mock_agent_service.update_agent.assert_called_once_with(
        "ws1",
        "Assistant",
        description="Updated",
        system_prompt=None,
        provider=None,
        model=None,
        allowed_tools=None,
    )


async def test_update_agent_not_found_returns_404(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.update_agent.side_effect = NotFoundError("agent", "missing")
    response = await api_client.patch("/workspaces/ws1/agents/missing", json={"description": "x"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /workspaces/{workspace_name}/agents/{agent_name}
# ---------------------------------------------------------------------------


async def test_delete_agent_returns_204(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.delete_agent.return_value = None
    response = await api_client.delete("/workspaces/ws1/agents/Assistant")
    assert response.status_code == 204


async def test_delete_agent_calls_service(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.delete_agent.return_value = None
    await api_client.delete("/workspaces/ws1/agents/Assistant")
    mock_agent_service.delete_agent.assert_called_once_with("ws1", "Assistant")


async def test_delete_agent_not_found_returns_404(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.delete_agent.side_effect = NotFoundError("agent", "missing")
    response = await api_client.delete("/workspaces/ws1/agents/missing")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /workspaces/{workspace_name}/agents/{agent_name}/chat
# ---------------------------------------------------------------------------


async def test_chat_returns_200(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.run_agent = AsyncMock(return_value=("Hello!", _FIXED_UUID))
    response = await api_client.post(
        "/workspaces/ws1/agents/Assistant/chat", json={"message": "Hi"}
    )
    assert response.status_code == 200


async def test_chat_returns_reply_and_conversation_id(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.run_agent = AsyncMock(return_value=("Hello!", _FIXED_UUID))
    response = await api_client.post(
        "/workspaces/ws1/agents/Assistant/chat", json={"message": "Hi"}
    )
    body = response.json()
    assert body["reply"] == "Hello!"
    assert body["conversation_id"] == str(_FIXED_UUID)


async def test_chat_calls_service(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.run_agent = AsyncMock(return_value=("Hello!", _FIXED_UUID))
    await api_client.post("/workspaces/ws1/agents/Assistant/chat", json={"message": "Hi"})
    mock_agent_service.run_agent.assert_called_once_with(
        "ws1", "Assistant", "Hi", conversation_id=None, session=None
    )


async def test_chat_with_conversation_id_passes_it_to_service(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.run_agent = AsyncMock(return_value=("Hello!", _FIXED_UUID))
    await api_client.post(
        "/workspaces/ws1/agents/Assistant/chat",
        json={"message": "Hi", "conversation_id": str(_FIXED_UUID)},
    )
    mock_agent_service.run_agent.assert_called_once_with(
        "ws1", "Assistant", "Hi", conversation_id=_FIXED_UUID, session=None
    )


async def test_chat_agent_not_found_returns_404(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.run_agent = AsyncMock(side_effect=NotFoundError("agent", "missing"))
    response = await api_client.post("/workspaces/ws1/agents/missing/chat", json={"message": "Hi"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /workspaces/{workspace_name}/agents/{agent_name}/reset
# ---------------------------------------------------------------------------


async def test_reset_returns_204(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.reset_agent.return_value = None
    response = await api_client.post("/workspaces/ws1/agents/Assistant/reset")
    assert response.status_code == 204


async def test_reset_calls_service_without_conversation_id(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.reset_agent.return_value = None
    await api_client.post("/workspaces/ws1/agents/Assistant/reset")
    mock_agent_service.reset_agent.assert_called_once_with("ws1", "Assistant", conversation_id=None)


async def test_reset_calls_service_with_conversation_id(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.reset_agent.return_value = None
    await api_client.post(
        "/workspaces/ws1/agents/Assistant/reset",
        json={"conversation_id": str(_FIXED_UUID)},
    )
    mock_agent_service.reset_agent.assert_called_once_with(
        "ws1", "Assistant", conversation_id=_FIXED_UUID
    )


async def test_reset_agent_not_found_returns_404(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.reset_agent.side_effect = NotFoundError("agent", "missing")
    response = await api_client.post("/workspaces/ws1/agents/missing/reset")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /workspaces/{workspace_name}/agents/{agent_name}/chat/stream
# ---------------------------------------------------------------------------


def _collect_sse(response: httpx.Response) -> list[str]:
    return [
        line.removeprefix("data: ")
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


async def test_chat_stream_returns_200(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    async def _tokens() -> AsyncIterator[str]:
        yield "Hello"
        yield " world"

    mock_agent_service.stream_agent = AsyncMock(return_value=(_tokens(), _FIXED_UUID))
    response = await api_client.post(
        "/workspaces/ws1/agents/Assistant/chat/stream", json={"message": "Hi"}
    )
    assert response.status_code == 200


async def test_chat_stream_content_type(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    async def _tokens() -> AsyncIterator[str]:
        yield "Hi"

    mock_agent_service.stream_agent = AsyncMock(return_value=(_tokens(), _FIXED_UUID))
    response = await api_client.post(
        "/workspaces/ws1/agents/Assistant/chat/stream", json={"message": "Hi"}
    )
    assert response.headers["content-type"].startswith("text/event-stream")


async def test_chat_stream_yields_tokens(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    async def _tokens() -> AsyncIterator[str]:
        yield "Hello"
        yield " world"

    mock_agent_service.stream_agent = AsyncMock(return_value=(_tokens(), _FIXED_UUID))
    response = await api_client.post(
        "/workspaces/ws1/agents/Assistant/chat/stream", json={"message": "Hi"}
    )
    assert _collect_sse(response) == ["Hello", " world", "[DONE]"]


async def test_chat_stream_returns_conversation_id_header(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    async def _tokens() -> AsyncIterator[str]:
        yield "ok"

    mock_agent_service.stream_agent = AsyncMock(return_value=(_tokens(), _FIXED_UUID))
    response = await api_client.post(
        "/workspaces/ws1/agents/Assistant/chat/stream", json={"message": "Hi"}
    )
    assert response.headers["x-conversation-id"] == str(_FIXED_UUID)


async def test_chat_stream_calls_service(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    async def _tokens() -> AsyncIterator[str]:
        yield "ok"

    mock_agent_service.stream_agent = AsyncMock(return_value=(_tokens(), _FIXED_UUID))
    await api_client.post("/workspaces/ws1/agents/Assistant/chat/stream", json={"message": "Hi"})
    mock_agent_service.stream_agent.assert_called_once_with(
        "ws1", "Assistant", "Hi", conversation_id=None, session=None
    )


async def test_chat_stream_agent_not_found_returns_404(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.stream_agent = AsyncMock(side_effect=NotFoundError("agent", "missing"))
    response = await api_client.post(
        "/workspaces/ws1/agents/missing/chat/stream", json={"message": "Hi"}
    )
    assert response.status_code == 404
