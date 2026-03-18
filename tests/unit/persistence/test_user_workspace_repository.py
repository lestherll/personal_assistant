"""Unit tests for pagination in user_workspace_repository.py."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from personal_assistant.persistence.user_workspace_repository import UserWorkspaceRepository


def _make_mock_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


def _scalars_all_result(items: list[object]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


@pytest.fixture
def mock_session() -> AsyncMock:
    return _make_mock_session()


@pytest.fixture
def repo(mock_session: AsyncMock) -> UserWorkspaceRepository:
    return UserWorkspaceRepository(mock_session)


class TestListWorkspaces:
    async def test_returns_workspace_rows(self, repo, mock_session):
        row = MagicMock()
        mock_session.execute.return_value = _scalars_all_result([row])

        result = await repo.list_workspaces(uuid.uuid4(), skip=1, limit=5)

        assert result == [row]

    async def test_applies_offset_and_limit(self, repo, mock_session):
        mock_session.execute.return_value = _scalars_all_result([])

        await repo.list_workspaces(uuid.uuid4(), skip=2, limit=7)

        stmt = mock_session.execute.call_args.args[0]
        sql = str(stmt)
        assert "OFFSET" in sql
        assert "LIMIT" in sql


class TestListAgents:
    async def test_returns_agent_rows(self, repo, mock_session):
        row = MagicMock()
        mock_session.execute.return_value = _scalars_all_result([row])

        result = await repo.list_agents(uuid.uuid4(), skip=0, limit=3)

        assert result == [row]

    async def test_applies_offset_and_limit(self, repo, mock_session):
        mock_session.execute.return_value = _scalars_all_result([])

        await repo.list_agents(uuid.uuid4(), skip=4, limit=9)

        stmt = mock_session.execute.call_args.args[0]
        sql = str(stmt)
        assert "OFFSET" in sql
        assert "LIMIT" in sql
