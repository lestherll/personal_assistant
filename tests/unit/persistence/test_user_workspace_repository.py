"""Unit tests for UserWorkspaceRepository."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from personal_assistant.persistence.models import UserAgent, UserWorkspace
from personal_assistant.persistence.user_workspace_repository import UserWorkspaceRepository


def _make_mock_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


def _scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


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


class TestWorkspaces:
    async def test_create_workspace_adds_commits_and_refreshes(self, repo, mock_session):
        ws = await repo.create_workspace(uuid.uuid4(), "default", "desc")

        assert isinstance(ws, UserWorkspace)
        assert ws.name == "default"
        mock_session.add.assert_called_once_with(ws)
        mock_session.commit.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(ws)

    async def test_get_workspace_returns_row(self, repo, mock_session):
        ws = UserWorkspace(user_id=uuid.uuid4(), name="default", description="desc")
        mock_session.execute.return_value = _scalar_result(ws)

        result = await repo.get_workspace(ws.user_id, "default")

        assert result is ws

    async def test_get_workspace_returns_none(self, repo, mock_session):
        mock_session.execute.return_value = _scalar_result(None)

        result = await repo.get_workspace(uuid.uuid4(), "missing")

        assert result is None

    async def test_list_workspaces_returns_workspace_rows(self, repo, mock_session):
        row = MagicMock()
        mock_session.execute.return_value = _scalars_all_result([row])

        result = await repo.list_workspaces(uuid.uuid4(), skip=1, limit=5)

        assert result == [row]

    async def test_list_workspaces_applies_offset_and_limit(self, repo, mock_session):
        mock_session.execute.return_value = _scalars_all_result([])

        await repo.list_workspaces(uuid.uuid4(), skip=2, limit=7)

        stmt = mock_session.execute.call_args.args[0]
        sql = str(stmt)
        assert "OFFSET" in sql
        assert "LIMIT" in sql

    async def test_list_workspaces_without_limit_omits_limit_clause(self, repo, mock_session):
        mock_session.execute.return_value = _scalars_all_result([])

        await repo.list_workspaces(uuid.uuid4(), skip=0, limit=None)

        stmt = mock_session.execute.call_args.args[0]
        assert "LIMIT -1 OFFSET" in str(stmt)

    async def test_delete_workspace_returns_false_when_missing(self, repo):
        with patch.object(repo, "get_workspace", AsyncMock(return_value=None)):
            deleted = await repo.delete_workspace(uuid.uuid4(), "missing")

        assert deleted is False

    async def test_delete_workspace_deletes_and_commits(self, repo, mock_session):
        ws = UserWorkspace(user_id=uuid.uuid4(), name="default", description="desc")
        with patch.object(repo, "get_workspace", AsyncMock(return_value=ws)):
            deleted = await repo.delete_workspace(ws.user_id, ws.name)

        assert deleted is True
        mock_session.delete.assert_awaited_once_with(ws)
        mock_session.commit.assert_awaited_once()

    async def test_upsert_workspace_creates_when_missing(self, repo):
        ws = UserWorkspace(user_id=uuid.uuid4(), name="default", description="desc")
        with (
            patch.object(repo, "get_workspace", AsyncMock(return_value=None)),
            patch.object(repo, "create_workspace", AsyncMock(return_value=ws)) as create_mock,
        ):
            result = await repo.upsert_workspace(ws.user_id, ws.name, ws.description)

        assert result is ws
        create_mock.assert_awaited_once_with(ws.user_id, ws.name, ws.description)

    async def test_upsert_workspace_updates_existing(self, repo, mock_session):
        ws = UserWorkspace(user_id=uuid.uuid4(), name="default", description="old")
        with patch.object(repo, "get_workspace", AsyncMock(return_value=ws)):
            result = await repo.upsert_workspace(ws.user_id, ws.name, "new")

        assert result is ws
        assert ws.description == "new"
        mock_session.commit.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(ws)


class TestAgents:
    async def test_create_agent_adds_commits_and_refreshes(self, repo, mock_session):
        agent = await repo.create_agent(
            user_workspace_id=uuid.uuid4(),
            name="assistant",
            description="desc",
            system_prompt="You are helpful",
            provider="anthropic",
            model="claude",
            allowed_tools=["search"],
        )

        assert isinstance(agent, UserAgent)
        assert agent.name == "assistant"
        mock_session.add.assert_called_once_with(agent)
        mock_session.commit.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(agent)

    async def test_get_agent_returns_row(self, repo, mock_session):
        agent = UserAgent(
            user_workspace_id=uuid.uuid4(),
            name="assistant",
            description="desc",
            system_prompt="prompt",
            provider=None,
            model=None,
            allowed_tools=None,
        )
        mock_session.execute.return_value = _scalar_result(agent)

        result = await repo.get_agent(agent.user_workspace_id, "assistant")

        assert result is agent

    async def test_get_agent_returns_none(self, repo, mock_session):
        mock_session.execute.return_value = _scalar_result(None)

        result = await repo.get_agent(uuid.uuid4(), "missing")

        assert result is None

    async def test_list_agents_returns_agent_rows(self, repo, mock_session):
        row = MagicMock()
        mock_session.execute.return_value = _scalars_all_result([row])

        result = await repo.list_agents(uuid.uuid4(), skip=0, limit=3)

        assert result == [row]

    async def test_list_agents_applies_offset_and_limit(self, repo, mock_session):
        mock_session.execute.return_value = _scalars_all_result([])

        await repo.list_agents(uuid.uuid4(), skip=4, limit=9)

        stmt = mock_session.execute.call_args.args[0]
        sql = str(stmt)
        assert "OFFSET" in sql
        assert "LIMIT" in sql

    async def test_list_agents_without_limit_omits_limit_clause(self, repo, mock_session):
        mock_session.execute.return_value = _scalars_all_result([])

        await repo.list_agents(uuid.uuid4(), skip=0, limit=None)

        stmt = mock_session.execute.call_args.args[0]
        assert "LIMIT -1 OFFSET" in str(stmt)

    async def test_delete_agent_returns_false_when_missing(self, repo):
        with patch.object(repo, "get_agent", AsyncMock(return_value=None)):
            deleted = await repo.delete_agent(uuid.uuid4(), "missing")

        assert deleted is False

    async def test_delete_agent_deletes_and_commits(self, repo, mock_session):
        agent = UserAgent(
            user_workspace_id=uuid.uuid4(),
            name="assistant",
            description="desc",
            system_prompt="prompt",
            provider=None,
            model=None,
            allowed_tools=None,
        )
        with patch.object(repo, "get_agent", AsyncMock(return_value=agent)):
            deleted = await repo.delete_agent(agent.user_workspace_id, agent.name)

        assert deleted is True
        mock_session.delete.assert_awaited_once_with(agent)
        mock_session.commit.assert_awaited_once()

    async def test_upsert_agent_creates_when_missing(self, repo):
        agent = UserAgent(
            user_workspace_id=uuid.uuid4(),
            name="assistant",
            description="desc",
            system_prompt="prompt",
            provider="anthropic",
            model="claude",
            allowed_tools=["search"],
        )
        with (
            patch.object(repo, "get_agent", AsyncMock(return_value=None)),
            patch.object(repo, "create_agent", AsyncMock(return_value=agent)) as create_mock,
        ):
            result = await repo.upsert_agent(
                user_workspace_id=agent.user_workspace_id,
                name=agent.name,
                description=agent.description,
                system_prompt=agent.system_prompt,
                provider=agent.provider,
                model=agent.model,
                allowed_tools=agent.allowed_tools,
            )

        assert result is agent
        create_mock.assert_awaited_once()

    async def test_upsert_agent_updates_existing(self, repo, mock_session):
        agent = UserAgent(
            user_workspace_id=uuid.uuid4(),
            name="assistant",
            description="old",
            system_prompt="old prompt",
            provider="anthropic",
            model="old-model",
            allowed_tools=["search"],
        )
        with patch.object(repo, "get_agent", AsyncMock(return_value=agent)):
            result = await repo.upsert_agent(
                user_workspace_id=agent.user_workspace_id,
                name=agent.name,
                description="new",
                system_prompt="new prompt",
                provider="ollama",
                model="new-model",
                allowed_tools=[],
            )

        assert result is agent
        assert agent.description == "new"
        assert agent.system_prompt == "new prompt"
        assert agent.provider == "ollama"
        assert agent.model == "new-model"
        assert agent.allowed_tools == []
        mock_session.commit.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(agent)
