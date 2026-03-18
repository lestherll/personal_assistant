"""Unit tests for APIKeyRepository."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from personal_assistant.persistence.api_key_repository import APIKeyRepository
from personal_assistant.persistence.models import UserAPIKey


def _make_mock_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _rowcount_result(count: int) -> MagicMock:
    result = MagicMock()
    result.rowcount = count
    return result


def _scalars_all_result(items: list[object]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


@pytest.fixture
def mock_session() -> AsyncMock:
    return _make_mock_session()


@pytest.fixture
def repo(mock_session: AsyncMock) -> APIKeyRepository:
    return APIKeyRepository(mock_session)


def _make_api_key(user_id: uuid.UUID, *, is_active: bool = True) -> UserAPIKey:
    return UserAPIKey(
        id=uuid.uuid4(),
        user_id=user_id,
        name="my-key",
        key_hash="old-hash",
        key_prefix="sk-old-1234",
        is_active=is_active,
        created_at=datetime.now(UTC),
    )


class TestCreate:
    async def test_create_adds_flushes_and_refreshes(self, repo, mock_session):
        user_id = uuid.uuid4()

        created = await repo.create(
            user_id=user_id,
            name="my-key",
            key_hash="hash-1",
            key_prefix="sk-hash-1",
        )

        assert created.user_id == user_id
        assert created.name == "my-key"
        mock_session.add.assert_called_once_with(created)
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(created)


class TestGetByHash:
    async def test_get_by_hash_returns_row(self, repo, mock_session):
        row = _make_api_key(uuid.uuid4())
        mock_session.execute.return_value = _scalar_result(row)

        result = await repo.get_by_hash("hash-1")

        assert result is row

    async def test_get_by_hash_returns_none_when_missing(self, repo, mock_session):
        mock_session.execute.return_value = _scalar_result(None)

        result = await repo.get_by_hash("missing")

        assert result is None


class TestListForUser:
    async def test_list_for_user_returns_rows(self, repo, mock_session):
        user_id = uuid.uuid4()
        row = _make_api_key(user_id)
        mock_session.execute.return_value = _scalars_all_result([row])

        result = await repo.list_for_user(user_id)

        assert result == [row]

    async def test_list_for_user_empty(self, repo, mock_session):
        mock_session.execute.return_value = _scalars_all_result([])

        result = await repo.list_for_user(uuid.uuid4())

        assert result == []


class TestRevoke:
    async def test_revoke_returns_true_and_flushes(self, repo, mock_session):
        mock_session.execute.return_value = _rowcount_result(1)

        revoked = await repo.revoke(uuid.uuid4(), uuid.uuid4())

        assert revoked is True
        mock_session.flush.assert_awaited_once()

    async def test_revoke_returns_false_when_missing(self, repo, mock_session):
        mock_session.execute.return_value = _rowcount_result(0)

        revoked = await repo.revoke(uuid.uuid4(), uuid.uuid4())

        assert revoked is False
        mock_session.flush.assert_awaited_once()


class TestRotate:
    async def test_rotate_revokes_current_and_creates_replacement(self, repo, mock_session):
        user_id = uuid.uuid4()
        current = _make_api_key(user_id)
        mock_session.execute.return_value = _scalar_result(current)

        created = await repo.rotate(
            user_id=user_id,
            key_id=current.id,
            new_key_hash="new-hash",
            new_key_prefix="sk-new-1234",
        )

        assert created is not None
        assert current.is_active is False
        assert created.user_id == user_id
        assert created.name == current.name
        assert created.key_hash == "new-hash"
        assert created.key_prefix == "sk-new-1234"
        mock_session.add.assert_called_once_with(created)
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(created)

    async def test_rotate_returns_none_when_key_not_found(self, repo, mock_session):
        mock_session.execute.return_value = _scalar_result(None)

        created = await repo.rotate(
            user_id=uuid.uuid4(),
            key_id=uuid.uuid4(),
            new_key_hash="new-hash",
            new_key_prefix="sk-new-1234",
        )

        assert created is None
        mock_session.add.assert_not_called()
        mock_session.flush.assert_not_awaited()
        mock_session.refresh.assert_not_awaited()
        stmt = mock_session.execute.call_args.args[0]
        sql = str(stmt)
        assert "expires_at" in sql
        assert "IS NULL" in sql


class TestUpdateLastUsed:
    async def test_update_last_used_executes_and_flushes(self, repo, mock_session):
        now = datetime.now(UTC)

        await repo.update_last_used(uuid.uuid4(), now)

        mock_session.execute.assert_awaited_once()
        mock_session.flush.assert_awaited_once()
