from unittest.mock import AsyncMock

import pytest

from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.services.exceptions import AlreadyExistsError, NotFoundError
from personal_assistant.services.views import WorkspaceChatView, WorkspaceDetailView, WorkspaceView
from personal_assistant.services.workspace_service import WorkspaceService
from tests.unit.conftest import make_mock_provider
from tests.unit.core.test_workspace import make_mock_agent


@pytest.fixture
def orchestrator():
    from personal_assistant.providers.registry import ProviderRegistry

    registry = ProviderRegistry()
    registry.register(make_mock_provider("mock"), default=True)
    return Orchestrator(registry)


@pytest.fixture
def service(orchestrator):
    return WorkspaceService(orchestrator)


class TestCreateWorkspace:
    def test_creates_and_returns_view(self, service):
        view = service.create_workspace("ws1", "First workspace")
        assert isinstance(view, WorkspaceView)
        assert view.name == "ws1"
        assert view.description == "First workspace"
        assert view.agents == []
        assert view.tools == []

    def test_stores_metadata(self, service):
        view = service.create_workspace("ws1", "desc", metadata={"key": "val"})
        assert view.metadata == {"key": "val"}

    def test_duplicate_name_raises(self, service):
        service.create_workspace("ws1", "desc")
        with pytest.raises(AlreadyExistsError):
            service.create_workspace("ws1", "other")


class TestListWorkspaces:
    def test_empty(self, service):
        assert service.list_workspaces() == []

    def test_returns_all(self, service):
        service.create_workspace("a", "")
        service.create_workspace("b", "")
        names = [v.name for v in service.list_workspaces()]
        assert set(names) == {"a", "b"}


class TestGetWorkspace:
    def test_returns_detail_view(self, service):
        service.create_workspace("ws1", "desc")
        view = service.get_workspace("ws1")
        assert isinstance(view, WorkspaceDetailView)
        assert view.name == "ws1"

    def test_includes_agents(self, service, orchestrator):
        service.create_workspace("ws1", "")
        ws = orchestrator.get_workspace("ws1")
        assert ws is not None
        ws.add_agent(make_mock_agent("Bot"))
        view = service.get_workspace("ws1")
        assert len(view.agents) == 1

    def test_not_found_raises(self, service):
        with pytest.raises(NotFoundError):
            service.get_workspace("ghost")


class TestUpdateWorkspace:
    def test_updates_description(self, service):
        service.create_workspace("ws1", "old")
        view = service.update_workspace("ws1", description="new")
        assert view.description == "new"

    def test_updates_metadata(self, service):
        service.create_workspace("ws1", "desc", metadata={"a": 1})
        view = service.update_workspace("ws1", metadata={"b": 2})
        assert view.metadata == {"b": 2}

    def test_partial_update_leaves_other_fields(self, service):
        service.create_workspace("ws1", "original", metadata={"x": 1})
        view = service.update_workspace("ws1", description="updated")
        assert view.description == "updated"
        assert view.metadata == {"x": 1}

    def test_not_found_raises(self, service):
        with pytest.raises(NotFoundError):
            service.update_workspace("ghost", description="x")


class TestDeleteWorkspace:
    def test_deletes_workspace(self, service, orchestrator):
        service.create_workspace("ws1", "")
        service.delete_workspace("ws1")
        assert orchestrator.get_workspace("ws1") is None

    def test_not_found_raises(self, service):
        with pytest.raises(NotFoundError):
            service.delete_workspace("ghost")

    def test_clears_active_workspace_when_deleted(self, service, orchestrator):
        service.create_workspace("ws1", "")
        service.delete_workspace("ws1")
        assert orchestrator.active_workspace is None

    def test_reassigns_active_to_remaining(self, service, orchestrator):
        service.create_workspace("ws1", "")
        service.create_workspace("ws2", "")
        service.delete_workspace("ws1")
        assert orchestrator.active_workspace is not None
        assert orchestrator.active_workspace.config.name == "ws2"


class TestChatWorkspace:
    async def test_chat_returns_workspace_chat_view(self, service, orchestrator):
        service.create_workspace("ws1", "desc")
        orchestrator.delegate_to_workspace = AsyncMock(return_value=("reply", "t1", "Bot"))
        view = await service.chat("ws1", "hello")
        assert isinstance(view, WorkspaceChatView)
        assert view.response == "reply"
        assert view.thread_id == "t1"
        assert view.agent_used == "Bot"

    async def test_chat_raises_not_found_for_missing_workspace(self, service):
        with pytest.raises(NotFoundError):
            await service.chat("ghost", "hello")

    async def test_chat_passes_thread_id(self, service, orchestrator):
        service.create_workspace("ws1", "desc")
        orchestrator.delegate_to_workspace = AsyncMock(return_value=("reply", "t1", "Bot"))
        await service.chat("ws1", "hello", thread_id="my-thread")
        orchestrator.delegate_to_workspace.assert_awaited_once_with(
            task="hello",
            workspace_name="ws1",
            thread_id="my-thread",
            session=None,
        )

    async def test_chat_passes_session(self, service, orchestrator):
        service.create_workspace("ws1", "desc")
        orchestrator.delegate_to_workspace = AsyncMock(return_value=("reply", "t1", "Bot"))
        fake_session = object()
        await service.chat("ws1", "hello", session=fake_session)
        orchestrator.delegate_to_workspace.assert_awaited_once_with(
            task="hello",
            workspace_name="ws1",
            thread_id=None,
            session=fake_session,
        )
