"""Unit tests for persistence/repository.py — all async, no live DB."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from personal_assistant.persistence.models import Conversation, Message
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
        await repo.create_conversation("Agent1", "workspace1")
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()
        mock_session.refresh.assert_awaited_once()

    async def test_returns_conversation(self, repo, mock_session):
        # refresh doesn't modify the object, so we can check the add call
        await repo.create_conversation("Agent1")
        mock_session.add.assert_called_once()
        added = mock_session.add.call_args[0][0]
        assert isinstance(added, Conversation)
        assert added.agent_name == "Agent1"


class TestGetConversation:
    async def test_returns_conversation_when_found(self, repo, mock_session):
        conv = Conversation(agent_name="Agent1")
        mock_session.execute.return_value = _scalar_result(conv)
        result = await repo.get_conversation(uuid.uuid4())
        assert result is conv

    async def test_returns_none_when_not_found(self, repo, mock_session):
        mock_session.execute.return_value = _scalar_result(None)
        result = await repo.get_conversation(uuid.uuid4())
        assert result is None


class TestTouchConversation:
    async def test_updates_updated_at_when_found(self, repo, mock_session):
        conv = Conversation(agent_name="Agent1")
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


class TestGetConversationForAgent:
    async def test_returns_conversation_on_match(self, repo, mock_session):
        conv = Conversation(agent_name="Agent1", workspace_name="ws1")
        mock_session.execute.return_value = _scalar_result(conv)
        result = await repo.get_conversation_for_agent(uuid.uuid4(), "Agent1", "ws1")
        assert result is conv

    async def test_returns_none_on_mismatch(self, repo, mock_session):
        mock_session.execute.return_value = _scalar_result(None)
        result = await repo.get_conversation_for_agent(uuid.uuid4(), "Agent1", "ws1")
        assert result is None


class TestSaveMessage:
    async def test_adds_and_commits(self, repo, mock_session):
        conv_id = uuid.uuid4()
        await repo.save_message(conv_id, "human", "Hello")
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

    async def test_returns_message_with_correct_role_and_content(self, repo, mock_session):
        conv_id = uuid.uuid4()
        result = await repo.save_message(conv_id, "ai", "Hi there")
        assert isinstance(result, Message)
        assert result.role == "ai"
        assert result.content == "Hi there"
        assert result.conversation_id == conv_id
