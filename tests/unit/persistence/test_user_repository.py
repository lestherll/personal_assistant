"""Unit tests for UserRepository."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from personal_assistant.persistence.models import User
from personal_assistant.persistence.user_repository import UserRepository


def _make_mock_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


@pytest.fixture
def mock_session() -> AsyncMock:
    return _make_mock_session()


@pytest.fixture
def repo(mock_session: AsyncMock) -> UserRepository:
    return UserRepository(mock_session)


class TestCreate:
    async def test_create_adds_commits_and_refreshes(self, repo, mock_session):
        user = await repo.create("alice", "alice@example.com", "hashed")

        assert isinstance(user, User)
        assert user.username == "alice"
        assert user.email == "alice@example.com"
        mock_session.add.assert_called_once_with(user)
        mock_session.commit.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(user)


class TestLookupMethods:
    async def test_get_by_id_returns_user(self, repo, mock_session):
        user = User(username="alice", email="alice@example.com", hashed_password="hashed")
        mock_session.execute.return_value = _scalar_result(user)

        result = await repo.get_by_id(uuid.uuid4())

        assert result is user

    async def test_get_by_id_returns_none(self, repo, mock_session):
        mock_session.execute.return_value = _scalar_result(None)

        result = await repo.get_by_id(uuid.uuid4())

        assert result is None

    async def test_get_by_username_returns_user(self, repo, mock_session):
        user = User(username="alice", email="alice@example.com", hashed_password="hashed")
        mock_session.execute.return_value = _scalar_result(user)

        result = await repo.get_by_username("alice")

        assert result is user

    async def test_get_by_username_returns_none(self, repo, mock_session):
        mock_session.execute.return_value = _scalar_result(None)

        result = await repo.get_by_username("ghost")

        assert result is None

    async def test_get_by_email_returns_user(self, repo, mock_session):
        user = User(username="alice", email="alice@example.com", hashed_password="hashed")
        mock_session.execute.return_value = _scalar_result(user)

        result = await repo.get_by_email("alice@example.com")

        assert result is user

    async def test_get_by_email_returns_none(self, repo, mock_session):
        mock_session.execute.return_value = _scalar_result(None)

        result = await repo.get_by_email("ghost@example.com")

        assert result is None
