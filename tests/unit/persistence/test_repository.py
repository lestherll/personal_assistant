"""Unit tests for persistence/repository.py — all async, no live DB."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from personal_assistant.persistence.models import Conversation, Message, MessageRole
from personal_assistant.persistence.repository import ConversationRepository


def _make_mock_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _scalar_result(value: object) -> MagicMock:
    """Return a mock that simulates execute().scalar_one_or_none()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _scalar_value(value: object) -> MagicMock:
    """Return a mock that simulates session.scalar()."""
    mock = AsyncMock(return_value=value)
    return mock


def _scalars_all_result(items: list) -> MagicMock:
    """Return a mock that simulates execute().scalars().all()."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> AsyncMock:
    return _make_mock_session()


@pytest.fixture
def repo(mock_session: AsyncMock) -> ConversationRepository:
    return ConversationRepository(mock_session)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateConversation:
    async def test_adds_and_commits_and_refreshes(self, repo, mock_session):
        ws_id = uuid.uuid4()
        await repo.create_conversation(ws_id)
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()
        mock_session.refresh.assert_awaited_once()

    async def test_returns_conversation_with_workspace_id(self, repo, mock_session):
        ws_id = uuid.uuid4()
        await repo.create_conversation(ws_id)
        mock_session.add.assert_called_once()
        added = mock_session.add.call_args[0][0]
        assert isinstance(added, Conversation)
        assert added.workspace_id == ws_id


class TestGetConversation:
    async def test_returns_conversation_when_found(self, repo, mock_session):
        conv = Conversation(workspace_id=uuid.uuid4())
        mock_session.execute.return_value = _scalar_result(conv)
        result = await repo.get_conversation(uuid.uuid4())
        assert result is conv

    async def test_returns_none_when_not_found(self, repo, mock_session):
        mock_session.execute.return_value = _scalar_result(None)
        result = await repo.get_conversation(uuid.uuid4())
        assert result is None


class TestTouchConversation:
    async def test_updates_updated_at_when_found(self, repo, mock_session):
        conv = Conversation(workspace_id=uuid.uuid4())
        conv.updated_at = None  # type: ignore[assignment]
        mock_session.execute.return_value = _scalar_result(conv)
        await repo.touch_conversation(uuid.uuid4())
        assert conv.updated_at is not None
        mock_session.commit.assert_awaited()

    async def test_no_op_when_not_found(self, repo, mock_session):
        mock_session.execute.return_value = _scalar_result(None)
        await repo.touch_conversation(uuid.uuid4())
        # commit should NOT be called if no conversation found
        mock_session.commit.assert_not_awaited()


class TestUpdateTitle:
    async def test_executes_update_and_flushes(self, repo, mock_session):
        conv_id = uuid.uuid4()
        await repo.update_title(conv_id, "Renamed")

        mock_session.execute.assert_awaited_once()
        stmt = mock_session.execute.call_args.args[0]
        sql = str(stmt)
        assert "UPDATE conversations" in sql
        assert "title" in sql
        assert "WHERE conversations.id" in sql
        mock_session.flush.assert_awaited_once()


class TestLoadMessages:
    async def test_returns_list_of_messages(self, repo, mock_session):
        msg1 = MagicMock(spec=Message)
        msg2 = MagicMock(spec=Message)
        mock_session.execute.return_value = _scalars_all_result([msg1, msg2])
        result = await repo.load_messages(uuid.uuid4())
        assert result == [msg1, msg2]

    async def test_returns_empty_list_when_none(self, repo, mock_session):
        mock_session.execute.return_value = _scalars_all_result([])
        result = await repo.load_messages(uuid.uuid4())
        assert result == []


class TestGetConversationForWorkspace:
    async def test_returns_conversation_on_match(self, repo, mock_session):
        ws_id = uuid.uuid4()
        conv = Conversation(workspace_id=ws_id)
        mock_session.execute.return_value = _scalar_result(conv)
        result = await repo.get_conversation_for_workspace(uuid.uuid4(), ws_id)
        assert result is conv

    async def test_returns_none_on_mismatch(self, repo, mock_session):
        mock_session.execute.return_value = _scalar_result(None)
        result = await repo.get_conversation_for_workspace(uuid.uuid4(), uuid.uuid4())
        assert result is None


class TestAddMessage:
    async def test_adds_and_commits(self, repo, mock_session):
        conv_id = uuid.uuid4()
        # Mock the two execute calls: with_for_update lock + sequence scalar
        mock_session.execute.return_value = MagicMock()
        mock_session.scalar.return_value = None  # no prior messages → seq 1
        await repo.add_message(conv_id, MessageRole.human, "Hello")
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

    async def test_returns_message_with_correct_role_and_content(self, repo, mock_session):
        conv_id = uuid.uuid4()
        mock_session.execute.return_value = MagicMock()
        mock_session.scalar.return_value = None
        result = await repo.add_message(conv_id, MessageRole.ai, "Hi there")
        assert isinstance(result, Message)
        assert result.role == MessageRole.ai
        assert result.content == "Hi there"
        assert result.conversation_id == conv_id

    async def test_sequence_index_increments(self, repo, mock_session):
        conv_id = uuid.uuid4()
        mock_session.execute.return_value = MagicMock()
        mock_session.scalar.return_value = 3  # existing max is 3
        result = await repo.add_message(conv_id, MessageRole.human, "Next")
        assert result.sequence_index == 4

    async def test_sequence_index_starts_at_one_when_empty(self, repo, mock_session):
        conv_id = uuid.uuid4()
        mock_session.execute.return_value = MagicMock()
        mock_session.scalar.return_value = None
        result = await repo.add_message(conv_id, MessageRole.human, "First")
        assert result.sequence_index == 1

    async def test_observability_fields_stored(self, repo, mock_session):
        conv_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        mock_session.execute.return_value = MagicMock()
        mock_session.scalar.return_value = None
        result = await repo.add_message(
            conv_id,
            MessageRole.ai,
            "Response",
            agent_id=agent_id,
            provider="anthropic",
            model="claude-sonnet-4-6",
            prompt_tokens=100,
            completion_tokens=50,
        )
        assert result.agent_id == agent_id
        assert result.provider == "anthropic"
        assert result.model == "claude-sonnet-4-6"
        assert result.prompt_tokens == 100
        assert result.completion_tokens == 50


class TestListConversations:
    async def test_returns_conversations(self, repo, mock_session):
        ws_id = uuid.uuid4()
        conv = Conversation(workspace_id=ws_id)
        mock_session.execute.return_value = _scalars_all_result([conv])
        result = await repo.list_conversations(ws_id)
        assert result == [conv]

    async def test_returns_empty_when_none(self, repo, mock_session):
        mock_session.execute.return_value = _scalars_all_result([])
        result = await repo.list_conversations(uuid.uuid4())
        assert result == []


class TestDeleteConversation:
    async def test_deletes_and_returns_true(self, repo, mock_session):
        conv = Conversation(workspace_id=uuid.uuid4())
        mock_session.execute.return_value = _scalar_result(conv)
        mock_session.delete = AsyncMock()
        result = await repo.delete_conversation(uuid.uuid4())
        assert result is True
        mock_session.delete.assert_awaited_once_with(conv)
        mock_session.commit.assert_awaited()

    async def test_returns_false_when_not_found(self, repo, mock_session):
        mock_session.execute.return_value = _scalar_result(None)
        result = await repo.delete_conversation(uuid.uuid4())
        assert result is False
