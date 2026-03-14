from unittest.mock import patch

import pytest

from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.services.agent_service import AgentService
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
    return AgentService(orchestrator)


@pytest.fixture
def workspace(orchestrator):
    from personal_assistant.core.workspace import WorkspaceConfig

    return orchestrator.create_workspace(WorkspaceConfig(name="ws", description="test ws"))


def _create_agent(service, workspace_name="ws", name="Bot", system_prompt="Be helpful."):
    mock = make_mock_graph()
    with patch("personal_assistant.core.agent.create_agent", return_value=mock):
        return service.create_agent(
            workspace_name,
            name=name,
            description="A test bot",
            system_prompt=system_prompt,
        )


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
    async def test_returns_string_response(self, service, workspace):
        _create_agent(service)
        response = await service.run_agent("ws", "Bot", "Hello")
        assert isinstance(response, str)
        assert response == "Test response"

    async def test_unknown_workspace_raises(self, service):
        with pytest.raises(NotFoundError):
            await service.run_agent("ghost", "Bot", "Hello")

    async def test_unknown_agent_raises(self, service, workspace):
        with pytest.raises(NotFoundError):
            await service.run_agent("ws", "ghost", "Hello")


class TestStreamAgent:
    async def test_yields_strings(self, service, workspace):
        _create_agent(service)
        chunks = [c async for c in service.stream_agent("ws", "Bot", "Hello")]
        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)

    async def test_unknown_workspace_raises(self, service):
        with pytest.raises(NotFoundError):
            async for _ in service.stream_agent("ghost", "Bot", "Hello"):
                pass

    async def test_unknown_agent_raises(self, service, workspace):
        with pytest.raises(NotFoundError):
            async for _ in service.stream_agent("ws", "ghost", "Hello"):
                pass


class TestResetAgent:
    async def test_clears_history(self, service, workspace):
        _create_agent(service)
        await service.run_agent("ws", "Bot", "Hello")
        ws_obj = service._orchestrator.get_workspace("ws")
        assert ws_obj is not None
        agent = ws_obj.get_agent("Bot")
        assert agent is not None
        assert len(agent.history) > 0
        service.reset_agent("ws", "Bot")
        assert agent.history == []

    def test_unknown_workspace_raises(self, service):
        with pytest.raises(NotFoundError):
            service.reset_agent("ghost", "Bot")

    def test_unknown_agent_raises(self, service, workspace):
        with pytest.raises(NotFoundError):
            service.reset_agent("ws", "ghost")
