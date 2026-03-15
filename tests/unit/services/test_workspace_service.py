"""Tests for the new DB-first, stateless WorkspaceService."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from personal_assistant.services.exceptions import (
    AlreadyExistsError,
    NotFoundError,
    ServiceValidationError,
)
from personal_assistant.services.views import WorkspaceChatView, WorkspaceDetailView, WorkspaceView
from tests.unit.conftest import make_mock_provider

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_id():
    return uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.fixture
def registry():
    from personal_assistant.providers.registry import ProviderRegistry

    reg = ProviderRegistry()
    reg.register(make_mock_provider("mock"), default=True)
    return reg


@pytest.fixture
def mock_agent_service():
    svc = MagicMock()
    svc.run_agent = AsyncMock(return_value=("Hello!", uuid.uuid4()))
    svc.stream_agent = AsyncMock()
    return svc


@pytest.fixture
def service(registry, mock_agent_service):
    from personal_assistant.services.workspace_service import WorkspaceService

    return WorkspaceService(registry, agent_service=mock_agent_service)


@pytest.fixture
def mock_ws_row(user_id):
    row = MagicMock()
    row.id = uuid.uuid4()
    row.user_id = user_id
    row.name = "ws"
    row.description = "test ws"
    return row


@pytest.fixture
def mock_agent_row(mock_ws_row):
    row = MagicMock()
    row.id = uuid.uuid4()
    row.user_workspace_id = mock_ws_row.id
    row.name = "Bot"
    row.description = "A bot"
    row.system_prompt = "Be helpful."
    row.provider = None
    row.model = None
    row.allowed_tools = []
    return row


def _mock_ws_repo(ws_row=None, ws_rows=None, agent_rows=None):
    repo = MagicMock()
    repo.get_workspace = AsyncMock(return_value=ws_row)
    repo.list_workspaces = AsyncMock(return_value=ws_rows or ([ws_row] if ws_row else []))
    repo.create_workspace = AsyncMock(return_value=ws_row)
    repo.upsert_workspace = AsyncMock(return_value=ws_row)
    repo.delete_workspace = AsyncMock(return_value=True)
    repo.list_agents = AsyncMock(return_value=agent_rows or [])
    return repo


def _patch_ws_repo(ws_repo):
    return patch(
        "personal_assistant.services.workspace_service.UserWorkspaceRepository",
        return_value=ws_repo,
    )


# ---------------------------------------------------------------------------
# CRUD: create_workspace
# ---------------------------------------------------------------------------


class TestCreateWorkspace:
    async def test_creates_and_returns_view(self, service, user_id, mock_ws_row):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_row=None)
        ws_repo.create_workspace = AsyncMock(return_value=mock_ws_row)

        with _patch_ws_repo(ws_repo):
            view = await service.create_workspace(user_id, "ws", "test ws", session=session)

        assert isinstance(view, WorkspaceView)
        assert view.name == "ws"
        assert view.description == "test ws"

    async def test_duplicate_raises(self, service, user_id, mock_ws_row):
        session = MagicMock()
        # get_workspace returns existing row → AlreadyExistsError
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row)

        with _patch_ws_repo(ws_repo), pytest.raises(AlreadyExistsError):
            await service.create_workspace(user_id, "ws", "desc", session=session)

    async def test_no_session_raises(self, service, user_id):
        with pytest.raises(NotFoundError):
            await service.create_workspace(user_id, "ws", "desc", session=None)


# ---------------------------------------------------------------------------
# CRUD: list_workspaces
# ---------------------------------------------------------------------------


class TestListWorkspaces:
    async def test_returns_all(self, service, user_id, mock_ws_row):
        session = MagicMock()
        second_row = MagicMock()
        second_row.name = "ws2"
        second_row.description = "second"
        ws_repo = _mock_ws_repo(ws_rows=[mock_ws_row, second_row])

        with _patch_ws_repo(ws_repo):
            views = await service.list_workspaces(user_id, session=session)

        assert len(views) == 2

    async def test_empty(self, service, user_id):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_rows=[])

        with _patch_ws_repo(ws_repo):
            views = await service.list_workspaces(user_id, session=session)

        assert views == []


# ---------------------------------------------------------------------------
# CRUD: get_workspace
# ---------------------------------------------------------------------------


class TestGetWorkspace:
    async def test_returns_detail_view(self, service, user_id, mock_ws_row):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row)

        with _patch_ws_repo(ws_repo):
            view = await service.get_workspace(user_id, "ws", session=session)

        assert isinstance(view, WorkspaceDetailView)
        assert view.name == "ws"

    async def test_not_found_raises(self, service, user_id):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_row=None)

        with _patch_ws_repo(ws_repo), pytest.raises(NotFoundError):
            await service.get_workspace(user_id, "ghost", session=session)


# ---------------------------------------------------------------------------
# CRUD: update_workspace
# ---------------------------------------------------------------------------


class TestUpdateWorkspace:
    async def test_updates_description(self, service, user_id, mock_ws_row):
        session = MagicMock()
        updated = MagicMock()
        updated.name = "ws"
        updated.description = "updated"
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row)
        ws_repo.upsert_workspace = AsyncMock(return_value=updated)

        with _patch_ws_repo(ws_repo):
            view = await service.update_workspace(
                user_id, "ws", description="updated", session=session
            )

        assert view.description == "updated"

    async def test_not_found_raises(self, service, user_id):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_row=None)

        with _patch_ws_repo(ws_repo), pytest.raises(NotFoundError):
            await service.update_workspace(user_id, "ghost", session=session)


# ---------------------------------------------------------------------------
# CRUD: delete_workspace
# ---------------------------------------------------------------------------


class TestDeleteWorkspace:
    async def test_deletes(self, service, user_id, mock_ws_row):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row)

        with _patch_ws_repo(ws_repo):
            await service.delete_workspace(user_id, "ws", session=session)

        ws_repo.delete_workspace.assert_called_once_with(user_id, "ws")

    async def test_not_found_raises(self, service, user_id):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_row=None)

        with _patch_ws_repo(ws_repo), pytest.raises(NotFoundError):
            await service.delete_workspace(user_id, "ghost", session=session)


# ---------------------------------------------------------------------------
# chat — agent-direct path
# ---------------------------------------------------------------------------


class TestChatAgentDirect:
    async def test_delegates_to_agent_service(
        self, service, user_id, mock_ws_row, mock_agent_service
    ):
        session = AsyncMock()
        conv_id = uuid.uuid4()
        mock_agent_service.run_agent = AsyncMock(return_value=("Hello!", conv_id))
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row)

        with _patch_ws_repo(ws_repo):
            view = await service.chat(user_id, "ws", "hi", agent_name="Bot", session=session)

        assert isinstance(view, WorkspaceChatView)
        assert view.response == "Hello!"
        assert view.conversation_id == str(conv_id)
        assert view.agent_used == "Bot"

    async def test_passes_conversation_id(self, service, user_id, mock_ws_row, mock_agent_service):
        session = AsyncMock()
        existing_conv_id = uuid.uuid4()
        mock_agent_service.run_agent = AsyncMock(return_value=("reply", existing_conv_id))
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row)

        with _patch_ws_repo(ws_repo):
            await service.chat(
                user_id,
                "ws",
                "hi",
                agent_name="Bot",
                conversation_id=str(existing_conv_id),
                session=session,
            )

        mock_agent_service.run_agent.assert_awaited_once()
        call_kwargs = mock_agent_service.run_agent.call_args
        assert call_kwargs.kwargs["conversation_id"] == existing_conv_id

    async def test_invalid_conversation_id_raises(self, service, user_id, mock_ws_row):
        session = AsyncMock()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row)

        with (
            _patch_ws_repo(ws_repo),
            pytest.raises(ServiceValidationError, match="not a valid UUID"),
        ):
            await service.chat(
                user_id,
                "ws",
                "hi",
                agent_name="Bot",
                conversation_id="not-a-uuid",
                session=session,
            )

    async def test_provider_without_agent_raises(self, service, user_id, mock_ws_row):
        session = AsyncMock()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row)

        with _patch_ws_repo(ws_repo), pytest.raises(ServiceValidationError):
            await service.chat(user_id, "ws", "hi", provider="anthropic", session=session)


# ---------------------------------------------------------------------------
# chat — supervisor path
# ---------------------------------------------------------------------------


class TestChatSupervisorPath:
    async def test_routes_and_delegates(
        self, service, user_id, mock_ws_row, mock_agent_row, mock_agent_service
    ):
        session = AsyncMock()
        conv_id = uuid.uuid4()
        mock_agent_service.run_agent = AsyncMock(return_value=("routed reply", conv_id))
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_rows=[mock_agent_row])

        with (
            _patch_ws_repo(ws_repo),
            patch(
                "personal_assistant.services.workspace_service.route",
                new=AsyncMock(return_value="Bot"),
            ),
        ):
            view = await service.chat(user_id, "ws", "help me", session=session)

        assert view.response == "routed reply"
        assert view.agent_used == "Bot"
        mock_agent_service.run_agent.assert_awaited_once()

    async def test_no_agents_raises(self, service, user_id, mock_ws_row):
        session = AsyncMock()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_rows=[])

        with _patch_ws_repo(ws_repo), pytest.raises(ServiceValidationError):
            await service.chat(user_id, "ws", "help me", session=session)

    async def test_workspace_not_found_raises(self, service, user_id):
        session = AsyncMock()
        ws_repo = _mock_ws_repo(ws_row=None)

        with _patch_ws_repo(ws_repo), pytest.raises(NotFoundError):
            await service.chat(user_id, "ghost", "hi", session=session)


# ---------------------------------------------------------------------------
# stream_chat
# ---------------------------------------------------------------------------


class TestStreamChat:
    async def test_requires_agent_name(self, service, user_id, mock_ws_row):
        session = AsyncMock()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row)

        with (
            _patch_ws_repo(ws_repo),
            pytest.raises(ServiceValidationError, match="requires agent_name"),
        ):
            await service.stream_chat(user_id, "ws", "hi", session=session)

    async def test_delegates_to_agent_service_stream(
        self, service, user_id, mock_ws_row, mock_agent_service
    ):
        session = AsyncMock()
        conv_id = uuid.uuid4()

        async def fake_tokens():
            yield "hello"
            yield " world"

        mock_agent_service.stream_agent = AsyncMock(return_value=(fake_tokens(), conv_id))
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row)

        with _patch_ws_repo(ws_repo):
            token_iter, returned_id, agent_used = await service.stream_chat(
                user_id, "ws", "hi", agent_name="Bot", session=session
            )

        assert returned_id == str(conv_id)
        assert agent_used == "Bot"
        tokens = [t async for t in token_iter]
        assert tokens == ["hello", " world"]

    async def test_invalid_conversation_id_raises(self, service, user_id, mock_ws_row):
        session = AsyncMock()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row)

        with (
            _patch_ws_repo(ws_repo),
            pytest.raises(ServiceValidationError, match="not a valid UUID"),
        ):
            await service.stream_chat(
                user_id,
                "ws",
                "hi",
                agent_name="Bot",
                conversation_id="bad-uuid",
                session=session,
            )
