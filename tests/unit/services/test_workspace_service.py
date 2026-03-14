from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.services.exceptions import (
    AlreadyExistsError,
    NotFoundError,
    ServiceValidationError,
)
from personal_assistant.services.views import WorkspaceChatView, WorkspaceDetailView, WorkspaceView
from personal_assistant.services.workspace_service import WorkspaceService
from tests.unit.conftest import make_mock_provider
from tests.unit.core.test_workspace import make_mock_agent


@contextmanager
def _patch_create_agent():
    from tests.unit.conftest import make_mock_graph

    mock = make_mock_graph()
    with patch("personal_assistant.core.agent.create_agent", return_value=mock):
        yield mock


@pytest.fixture
def orchestrator():
    from personal_assistant.providers.registry import ProviderRegistry

    registry = ProviderRegistry()
    registry.register(make_mock_provider("mock"), default=True)
    return Orchestrator(registry)


@pytest.fixture
def service(orchestrator):
    return WorkspaceService(orchestrator)


@pytest.fixture
def service_with_conv(orchestrator):
    mock_conv_service = MagicMock()
    mock_conv_service.get_or_create_clone = AsyncMock()
    return WorkspaceService(orchestrator, mock_conv_service), mock_conv_service


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


class TestChatWorkspaceSupervisor:
    async def test_chat_returns_workspace_chat_view(self, service, orchestrator):
        service.create_workspace("ws1", "desc")
        orchestrator.delegate_to_workspace = AsyncMock(return_value=("reply", "t1", "Bot"))
        view = await service.chat("ws1", "hello")
        assert isinstance(view, WorkspaceChatView)
        assert view.response == "reply"
        assert view.conversation_id == "t1"
        assert view.agent_used == "Bot"

    async def test_chat_raises_not_found_for_missing_workspace(self, service):
        with pytest.raises(NotFoundError):
            await service.chat("ghost", "hello")

    async def test_chat_passes_conversation_id(self, service, orchestrator):
        service.create_workspace("ws1", "desc")
        orchestrator.delegate_to_workspace = AsyncMock(return_value=("reply", "t1", "Bot"))
        await service.chat("ws1", "hello", conversation_id="my-thread")
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

    async def test_provider_without_agent_name_raises(self, service, orchestrator):
        service.create_workspace("ws1", "desc")
        with pytest.raises(ServiceValidationError):
            await service.chat("ws1", "hello", provider="anthropic")

    async def test_model_without_agent_name_raises(self, service, orchestrator):
        service.create_workspace("ws1", "desc")
        with pytest.raises(ServiceValidationError):
            await service.chat("ws1", "hello", model="claude-opus-4-6")


class TestChatWorkspaceAgentDirect:
    async def test_chat_with_agent_name_calls_conv_service(self, orchestrator, service_with_conv):
        service, mock_conv = service_with_conv
        service.create_workspace("ws1", "desc")
        import uuid

        from personal_assistant.core.agent import Agent

        mock_clone = MagicMock(spec=Agent)
        mock_clone.run = AsyncMock(return_value="hello from bot")
        conv_id = uuid.uuid4()
        mock_conv.get_or_create_clone.return_value = (mock_clone, conv_id)

        view = await service.chat("ws1", "hi", agent_name="Bot")
        assert view.response == "hello from bot"
        assert view.agent_used == "Bot"
        assert view.conversation_id == str(conv_id)

    async def test_chat_with_invalid_conversation_id_raises(self, orchestrator, service_with_conv):
        service, _ = service_with_conv
        service.create_workspace("ws1", "desc")
        with pytest.raises(ServiceValidationError, match="not a valid UUID"):
            await service.chat("ws1", "hi", agent_name="Bot", conversation_id="not-a-uuid")

    async def test_chat_without_conv_service_raises(self, service, orchestrator):
        service.create_workspace("ws1", "desc")
        with pytest.raises(ServiceValidationError):
            await service.chat("ws1", "hi", agent_name="Bot")

    async def test_chat_with_provider_override(self, orchestrator, service_with_conv):
        service, mock_conv = service_with_conv
        service.create_workspace("ws1", "desc")

        import uuid

        from langchain_core.language_models import BaseChatModel

        from personal_assistant.core.agent import Agent

        mock_llm = MagicMock(spec=BaseChatModel)
        mock_provider = make_mock_provider("mock")
        mock_provider.get_model.return_value = mock_llm

        mock_clone = MagicMock(spec=Agent)
        mock_clone.run = AsyncMock(return_value="overridden response")
        conv_id = uuid.uuid4()
        mock_conv.get_or_create_clone.return_value = (mock_clone, conv_id)

        view = await service.chat(
            "ws1", "hi", agent_name="Bot", provider="mock", model="mock-model"
        )
        assert view.response == "overridden response"
        _, call_kwargs = mock_conv.get_or_create_clone.call_args
        assert call_kwargs.get("llm_override") is not None


class TestStreamChat:
    async def test_stream_chat_without_agent_name_raises(self, orchestrator, service_with_conv):
        service, _ = service_with_conv
        service.create_workspace("ws1", "desc")
        with pytest.raises(ServiceValidationError, match="requires agent_name"):
            await service.stream_chat("ws1", "hello")

    async def test_stream_chat_returns_tuple(self, orchestrator, service_with_conv):
        service, mock_conv = service_with_conv
        service.create_workspace("ws1", "desc")

        import uuid

        from langchain_core.messages import AIMessage

        from personal_assistant.core.agent import Agent

        async def fake_stream(msg, session):
            yield AIMessage(content="token1")
            yield AIMessage(content="token2")

        mock_clone = MagicMock(spec=Agent)
        mock_clone.stream = fake_stream
        conv_id = uuid.uuid4()
        mock_conv.get_or_create_clone.return_value = (mock_clone, conv_id)

        token_iter, returned_conv_id, agent_used = await service.stream_chat(
            "ws1", "hello", agent_name="Bot"
        )
        assert returned_conv_id == str(conv_id)
        assert agent_used == "Bot"
        tokens = [t async for t in token_iter]
        assert tokens == ["token1", "token2"]

    async def test_stream_chat_invalid_conversation_id_raises(
        self, orchestrator, service_with_conv
    ):
        service, _ = service_with_conv
        service.create_workspace("ws1", "desc")
        with pytest.raises(ServiceValidationError, match="not a valid UUID"):
            await service.stream_chat("ws1", "hello", agent_name="Bot", conversation_id="bad-uuid")
