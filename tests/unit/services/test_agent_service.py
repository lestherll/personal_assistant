from unittest.mock import patch

import pytest

from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.services.agent_service import AgentService
from personal_assistant.services.conversation_pool import ConversationPool
from personal_assistant.services.conversation_service import ConversationService
from personal_assistant.services.exceptions import AlreadyExistsError, NotFoundError
from personal_assistant.services.views import AgentView
from tests.unit.conftest import make_mock_graph, make_mock_provider


@pytest.fixture
def orchestrator():
    from personal_assistant.providers.registry import ProviderRegistry

    registry = ProviderRegistry()
    registry.register(make_mock_provider("mock"), default=True)
    return Orchestrator(registry)


@pytest.fixture
def service(orchestrator):
    pool = ConversationPool()
    conv_service = ConversationService(orchestrator, pool)
    return AgentService(orchestrator, conv_service)


@pytest.fixture
def workspace(orchestrator):
    from personal_assistant.core.workspace import WorkspaceConfig

    return orchestrator.create_workspace(WorkspaceConfig(name="ws", description="test ws"))


def _create_agent(service, workspace_name="ws", name="Bot", system_prompt="Be helpful."):
    """Create an agent in the service. The patch must remain active for clone() calls."""
    mock = make_mock_graph()
    with patch("personal_assistant.core.agent.create_agent", return_value=mock):
        return service.create_agent(
            workspace_name,
            name=name,
            description="A test bot",
            system_prompt=system_prompt,
        )


def _make_graph_patcher():
    """Return a context manager that patches create_agent for the duration of a run."""
    mock = make_mock_graph()
    return patch("personal_assistant.core.agent.create_agent", return_value=mock), mock


class TestCreateAgent:
    def test_creates_and_returns_view(self, service, workspace):
        view = _create_agent(service)
        assert isinstance(view, AgentView)
        assert view.config.name == "Bot"
        assert view.config.system_prompt == "Be helpful."

    def test_includes_llm_info(self, service, workspace):
        view = _create_agent(service)
        assert "source" in view.llm_info

    def test_unknown_workspace_raises(self, service):
        with pytest.raises(NotFoundError):
            _create_agent(service, workspace_name="ghost")

    def test_duplicate_agent_name_raises(self, service, workspace):
        _create_agent(service)
        with pytest.raises(AlreadyExistsError):
            _create_agent(service)


class TestListAgents:
    def test_empty_workspace(self, service, workspace):
        assert service.list_agents("ws") == []

    def test_returns_all_agents(self, service, workspace):
        _create_agent(service, name="Alpha")
        _create_agent(service, name="Beta")
        views = service.list_agents("ws")
        names = [v.config.name for v in views]
        assert set(names) == {"Alpha", "Beta"}

    def test_unknown_workspace_raises(self, service):
        with pytest.raises(NotFoundError):
            service.list_agents("ghost")


class TestGetAgent:
    def test_returns_view(self, service, workspace):
        _create_agent(service)
        view = service.get_agent("ws", "Bot")
        assert view.config.name == "Bot"

    def test_unknown_workspace_raises(self, service):
        with pytest.raises(NotFoundError):
            service.get_agent("ghost", "Bot")

    def test_unknown_agent_raises(self, service, workspace):
        with pytest.raises(NotFoundError):
            service.get_agent("ws", "ghost")


class TestUpdateAgent:
    def test_updates_system_prompt(self, service, workspace):
        _create_agent(service)
        mock = make_mock_graph()
        with patch("personal_assistant.core.agent.create_agent", return_value=mock):
            view = service.update_agent("ws", "Bot", system_prompt="New prompt.")
        assert view.config.system_prompt == "New prompt."

    def test_partial_update_preserves_other_fields(self, service, workspace):
        _create_agent(service, system_prompt="Original.")
        mock = make_mock_graph()
        with patch("personal_assistant.core.agent.create_agent", return_value=mock):
            view = service.update_agent("ws", "Bot", description="Updated desc")
        assert view.config.description == "Updated desc"
        assert view.config.system_prompt == "Original."

    def test_unknown_workspace_raises(self, service):
        with pytest.raises(NotFoundError):
            service.update_agent("ghost", "Bot", description="x")

    def test_unknown_agent_raises(self, service, workspace):
        with pytest.raises(NotFoundError):
            service.update_agent("ws", "ghost", description="x")


class TestDeleteAgent:
    def test_removes_agent(self, service, workspace, orchestrator):
        _create_agent(service)
        service.delete_agent("ws", "Bot")
        ws = orchestrator.get_workspace("ws")
        assert ws is not None
        assert ws.get_agent("Bot") is None

    def test_unknown_workspace_raises(self, service):
        with pytest.raises(NotFoundError):
            service.delete_agent("ghost", "Bot")

    def test_unknown_agent_raises(self, service, workspace):
        with pytest.raises(NotFoundError):
            service.delete_agent("ws", "ghost")


class TestRunAgent:
    async def test_returns_reply_and_conversation_id(self, service, workspace):
        import uuid

        patcher, _ = _make_graph_patcher()
        with patcher:
            _create_agent(service)
            reply, conv_id = await service.run_agent(
                "ws", "Bot", "Hello", conversation_id=None, session=None
            )
        assert isinstance(reply, str)
        assert reply == "Test response"
        assert isinstance(conv_id, uuid.UUID)

    async def test_unknown_workspace_raises(self, service):
        with pytest.raises(NotFoundError):
            await service.run_agent("ghost", "Bot", "Hello", conversation_id=None, session=None)

    async def test_unknown_agent_raises(self, service, workspace):
        with pytest.raises(NotFoundError):
            await service.run_agent("ws", "ghost", "Hello", conversation_id=None, session=None)

    async def test_template_history_stays_empty(self, service, workspace):
        """Template agents must not accumulate history — clones do."""
        patcher, _ = _make_graph_patcher()
        with patcher:
            _create_agent(service)
            await service.run_agent("ws", "Bot", "Hello", conversation_id=None, session=None)
        ws_obj = service._orchestrator.get_workspace("ws")
        assert ws_obj is not None
        template = ws_obj.get_agent("Bot")
        assert template is not None
        assert template.history == []


class TestStreamAgent:
    async def test_returns_iterator_and_conversation_id(self, service, workspace):
        import uuid

        patcher, _ = _make_graph_patcher()
        with patcher:
            _create_agent(service)
            tokens, conv_id = await service.stream_agent(
                "ws", "Bot", "Hello", conversation_id=None, session=None
            )
            assert isinstance(conv_id, uuid.UUID)
            chunks = [c async for c in tokens]
        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)

    async def test_unknown_workspace_raises(self, service):
        with pytest.raises(NotFoundError):
            await service.stream_agent("ghost", "Bot", "Hello", conversation_id=None, session=None)

    async def test_unknown_agent_raises(self, service, workspace):
        with pytest.raises(NotFoundError):
            await service.stream_agent("ws", "ghost", "Hello", conversation_id=None, session=None)


class TestResetAgent:
    def test_resets_template_when_no_conversation_id(self, service, workspace):
        _create_agent(service)
        # Should complete without error; template history is already empty
        service.reset_agent("ws", "Bot")
        ws_obj = service._orchestrator.get_workspace("ws")
        assert ws_obj is not None
        assert ws_obj.get_agent("Bot") is not None

    async def test_evicts_clone_when_conversation_id_given(self, service, workspace):
        patcher, _ = _make_graph_patcher()
        with patcher:
            _create_agent(service)
            _, conv_id = await service.run_agent(
                "ws", "Bot", "Hello", conversation_id=None, session=None
            )
        # Clone should be in pool
        pool = service._conversation_service._pool
        assert pool.get("ws", "Bot", conv_id) is not None

        service.reset_agent("ws", "Bot", conversation_id=conv_id)
        # Clone should be evicted
        assert pool.get("ws", "Bot", conv_id) is None

    def test_unknown_workspace_raises(self, service):
        with pytest.raises(NotFoundError):
            service.reset_agent("ghost", "Bot")

    def test_unknown_agent_raises(self, service, workspace):
        with pytest.raises(NotFoundError):
            service.reset_agent("ws", "ghost")
