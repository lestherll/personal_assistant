"""Unit tests for api/routers/agents.py."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx

from personal_assistant.services.exceptions import AlreadyExistsError, NotFoundError
from personal_assistant.services.views import ConversationView
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
    from api.dependencies import DEV_USER

    mock_agent_service.create_agent.return_value = make_agent_view()
    await api_client.post("/workspaces/ws1/agents/", json=_CREATE_BODY)
    mock_agent_service.create_agent.assert_called_once()
    call_args = mock_agent_service.create_agent.call_args
    assert call_args.args[0] == DEV_USER.id
    call_kwargs = call_args.kwargs
    assert call_kwargs["workspace_name"] == "ws1"
    assert call_kwargs["name"] == "Assistant"
    assert call_kwargs["description"] == "General agent"
    assert call_kwargs["system_prompt"] == "You are helpful."
    assert call_kwargs["provider"] is None
    assert call_kwargs["model"] is None
    assert call_kwargs["allowed_tools"] is None


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
    mock_agent_service.update_agent.assert_called_once()
    call_kwargs = mock_agent_service.update_agent.call_args.kwargs
    assert call_kwargs["description"] == "Updated"
    assert call_kwargs["system_prompt"] is None
    assert call_kwargs["provider"] is None
    assert call_kwargs["model"] is None
    assert call_kwargs["allowed_tools"] is None


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
    from api.dependencies import DEV_USER

    mock_agent_service.delete_agent.return_value = None
    await api_client.delete("/workspaces/ws1/agents/Assistant")
    mock_agent_service.delete_agent.assert_called_once()
    call_args = mock_agent_service.delete_agent.call_args
    assert call_args.args[0] == DEV_USER.id
    assert call_args.args[1:3] == ("ws1", "Assistant")


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
    from api.dependencies import DEV_USER

    mock_agent_service.run_agent = AsyncMock(return_value=("Hello!", _FIXED_UUID))
    await api_client.post("/workspaces/ws1/agents/Assistant/chat", json={"message": "Hi"})
    mock_agent_service.run_agent.assert_called_once_with(
        DEV_USER.id, "ws1", "Assistant", "Hi", conversation_id=None, session=None
    )


async def test_chat_with_conversation_id_passes_it_to_service(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    from api.dependencies import DEV_USER

    mock_agent_service.run_agent = AsyncMock(return_value=("Hello!", _FIXED_UUID))
    await api_client.post(
        "/workspaces/ws1/agents/Assistant/chat",
        json={"message": "Hi", "conversation_id": str(_FIXED_UUID)},
    )
    mock_agent_service.run_agent.assert_called_once_with(
        DEV_USER.id, "ws1", "Assistant", "Hi", conversation_id=_FIXED_UUID, session=None
    )


async def test_chat_agent_not_found_returns_404(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.run_agent = AsyncMock(side_effect=NotFoundError("agent", "missing"))
    response = await api_client.post("/workspaces/ws1/agents/missing/chat", json={"message": "Hi"})
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
    from api.dependencies import DEV_USER

    async def _tokens() -> AsyncIterator[str]:
        yield "ok"

    mock_agent_service.stream_agent = AsyncMock(return_value=(_tokens(), _FIXED_UUID))
    await api_client.post("/workspaces/ws1/agents/Assistant/chat/stream", json={"message": "Hi"})
    mock_agent_service.stream_agent.assert_called_once_with(
        DEV_USER.id, "ws1", "Assistant", "Hi", conversation_id=None, session=None
    )


async def test_chat_stream_agent_not_found_returns_404(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    mock_agent_service.stream_agent = AsyncMock(side_effect=NotFoundError("agent", "missing"))
    response = await api_client.post(
        "/workspaces/ws1/agents/missing/chat/stream", json={"message": "Hi"}
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /workspaces/{workspace_name}/agents/{agent_name}/conversations
# ---------------------------------------------------------------------------

_NOW = datetime.now(UTC)


def make_conv_view(conv_id: uuid.UUID | None = None) -> ConversationView:
    return ConversationView(
        id=conv_id or uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        user_id=None,
        created_at=_NOW,
        updated_at=_NOW,
    )


async def test_list_conversations_returns_200(
    api_client: httpx.AsyncClient, mock_agent_service: MagicMock
) -> None:
    # Without a DB session the endpoint returns 200 with an empty list
    mock_agent_service.list_conversations = AsyncMock(return_value=[make_conv_view()])
    response = await api_client.get("/workspaces/ws1/agents/Assistant/conversations")
    assert response.status_code == 200


async def test_list_conversations_returns_empty_without_db(
    mock_workspace_service: MagicMock,
    mock_agent_service: MagicMock,
) -> None:
    """When no DB session is available, the endpoint returns an empty list."""
    from fastapi import FastAPI
    from httpx import ASGITransport

    from api.dependencies import (
        DEV_USER,
        get_agent_service,
        get_current_user,
        get_db_session,
        get_workspace_service,
    )
    from api.exception_handlers import register_exception_handlers
    from api.routers import agents, workspaces

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(workspaces.router)
    app.include_router(agents.router)
    app.dependency_overrides[get_workspace_service] = lambda: mock_workspace_service
    app.dependency_overrides[get_agent_service] = lambda: mock_agent_service
    app.dependency_overrides[get_db_session] = lambda: None  # No DB
    app.dependency_overrides[get_current_user] = lambda: DEV_USER

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/workspaces/ws1/agents/Assistant/conversations")

    assert response.status_code == 200
    assert response.json() == []


async def test_list_conversations_returns_items(
    mock_workspace_service: MagicMock,
    mock_agent_service: MagicMock,
) -> None:
    """When a DB session is available, the service is called and results returned."""
    from unittest.mock import MagicMock as MM

    from fastapi import FastAPI
    from httpx import ASGITransport
    from sqlalchemy.ext.asyncio import AsyncSession

    from api.dependencies import (
        DEV_USER,
        get_agent_service,
        get_current_user,
        get_db_session,
        get_workspace_service,
    )
    from api.exception_handlers import register_exception_handlers
    from api.routers import agents, workspaces

    mock_db = MM(spec=AsyncSession)
    conv_id = uuid.uuid4()
    mock_agent_service.list_conversations = AsyncMock(return_value=[make_conv_view(conv_id)])

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(workspaces.router)
    app.include_router(agents.router)
    app.dependency_overrides[get_workspace_service] = lambda: mock_workspace_service
    app.dependency_overrides[get_agent_service] = lambda: mock_agent_service
    app.dependency_overrides[get_db_session] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: DEV_USER

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/workspaces/ws1/agents/Assistant/conversations")

    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(conv_id)


async def test_list_conversations_agent_not_found_returns_404(
    mock_workspace_service: MagicMock,
    mock_agent_service: MagicMock,
) -> None:
    mock_agent_service.list_conversations = AsyncMock(side_effect=NotFoundError("agent", "missing"))
    async with await _make_client_with_db(mock_workspace_service, mock_agent_service) as client:
        response = await client.get("/workspaces/ws1/agents/missing/conversations")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /workspaces/{workspace_name}/agents/{agent_name}/conversations/{id}
# ---------------------------------------------------------------------------


async def _make_client_with_db(
    mock_workspace_service: MagicMock,
    mock_agent_service: MagicMock,
) -> httpx.AsyncClient:
    """Create a test client with a mock DB session."""
    from unittest.mock import MagicMock as MM

    from fastapi import FastAPI
    from httpx import ASGITransport
    from sqlalchemy.ext.asyncio import AsyncSession

    from api.dependencies import (
        DEV_USER,
        get_agent_service,
        get_current_user,
        get_db_session,
        get_workspace_service,
    )
    from api.exception_handlers import register_exception_handlers
    from api.routers import agents, workspaces

    mock_db = MM(spec=AsyncSession)

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(workspaces.router)
    app.include_router(agents.router)
    app.dependency_overrides[get_workspace_service] = lambda: mock_workspace_service
    app.dependency_overrides[get_agent_service] = lambda: mock_agent_service
    app.dependency_overrides[get_db_session] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: DEV_USER
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_delete_conversation_returns_204(
    mock_workspace_service: MagicMock,
    mock_agent_service: MagicMock,
) -> None:
    mock_agent_service.delete_conversation = AsyncMock(return_value=None)
    async with await _make_client_with_db(mock_workspace_service, mock_agent_service) as client:
        response = await client.delete(
            f"/workspaces/ws1/agents/Assistant/conversations/{_FIXED_UUID}"
        )
    assert response.status_code == 204


async def test_delete_conversation_calls_service(
    mock_workspace_service: MagicMock,
    mock_agent_service: MagicMock,
) -> None:
    from api.dependencies import DEV_USER

    mock_agent_service.delete_conversation = AsyncMock(return_value=None)
    async with await _make_client_with_db(mock_workspace_service, mock_agent_service) as client:
        await client.delete(f"/workspaces/ws1/agents/Assistant/conversations/{_FIXED_UUID}")
    mock_agent_service.delete_conversation.assert_called_once()
    call_args = mock_agent_service.delete_conversation.call_args
    assert call_args.args[0] == DEV_USER.id
    assert call_args.args[1] == "ws1"
    assert call_args.args[2] == _FIXED_UUID


async def test_delete_conversation_not_found_returns_404(
    mock_workspace_service: MagicMock,
    mock_agent_service: MagicMock,
) -> None:
    mock_agent_service.delete_conversation = AsyncMock(
        side_effect=NotFoundError("conversation", str(_FIXED_UUID))
    )
    async with await _make_client_with_db(mock_workspace_service, mock_agent_service) as client:
        response = await client.delete(
            f"/workspaces/ws1/agents/Assistant/conversations/{_FIXED_UUID}"
        )
    assert response.status_code == 404


async def test_delete_conversation_no_db_returns_404(
    mock_workspace_service: MagicMock,
    mock_agent_service: MagicMock,
) -> None:
    """DELETE without a DB session should return 404."""
    from fastapi import FastAPI
    from httpx import ASGITransport

    from api.dependencies import (
        DEV_USER,
        get_agent_service,
        get_current_user,
        get_db_session,
        get_workspace_service,
    )
    from api.exception_handlers import register_exception_handlers
    from api.routers import agents, workspaces

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(workspaces.router)
    app.include_router(agents.router)
    app.dependency_overrides[get_workspace_service] = lambda: mock_workspace_service
    app.dependency_overrides[get_agent_service] = lambda: mock_agent_service
    app.dependency_overrides[get_db_session] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: DEV_USER

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.delete(
            f"/workspaces/ws1/agents/Assistant/conversations/{_FIXED_UUID}"
        )

    assert response.status_code == 404
