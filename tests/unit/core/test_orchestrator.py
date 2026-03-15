from unittest.mock import patch

import pytest

from personal_assistant.core.agent import AgentConfig, AgentRunResult
from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.core.workspace import WorkspaceConfig
from personal_assistant.providers.registry import ProviderRegistry
from tests.unit.conftest import make_mock_graph, make_mock_provider
from tests.unit.core.test_workspace import make_mock_agent


@pytest.fixture
def registry():
    r = ProviderRegistry()
    r.register(make_mock_provider("mock"), default=True)
    return r


@pytest.fixture
def orchestrator(registry):
    return Orchestrator(registry)


@pytest.fixture
def workspace_config():
    return WorkspaceConfig(name="test", description="Test workspace")


class TestWorkspaceManagement:
    def test_create_workspace(self, orchestrator, workspace_config) -> None:
        orchestrator.create_workspace(workspace_config)
        assert "test" in orchestrator.list_workspaces()

    def test_first_workspace_becomes_active(self, orchestrator, workspace_config) -> None:
        orchestrator.create_workspace(workspace_config)
        assert orchestrator._active_workspace == "test"

    def test_second_workspace_does_not_override_active(self, orchestrator) -> None:
        orchestrator.create_workspace(WorkspaceConfig(name="first", description=""))
        orchestrator.create_workspace(WorkspaceConfig(name="second", description=""))
        assert orchestrator._active_workspace == "first"

    def test_set_active_workspace(self, orchestrator) -> None:
        orchestrator.create_workspace(WorkspaceConfig(name="ws1", description=""))
        orchestrator.create_workspace(WorkspaceConfig(name="ws2", description=""))
        orchestrator.set_active_workspace("ws2")
        assert orchestrator._active_workspace == "ws2"

    def test_set_nonexistent_workspace_raises(self, orchestrator) -> None:
        with pytest.raises(ValueError, match="does not exist"):
            orchestrator.set_active_workspace("ghost")

    def test_get_workspace(self, orchestrator, workspace_config) -> None:
        ws = orchestrator.create_workspace(workspace_config)
        assert orchestrator.get_workspace("test") is ws

    def test_active_workspace_property(self, orchestrator, workspace_config) -> None:
        ws = orchestrator.create_workspace(workspace_config)
        assert orchestrator.active_workspace is ws

    def test_active_workspace_none_when_empty(self, orchestrator) -> None:
        assert orchestrator.active_workspace is None


class TestDelegation:
    async def test_delegate_routes_to_first_agent(
        self, orchestrator, workspace_config, mock_graph
    ) -> None:
        from unittest.mock import AsyncMock

        def _make_result(content: str) -> AgentRunResult:
            return AgentRunResult(
                content=content,
                agent_used="Alpha",
                provider=None,
                model=None,
                prompt_tokens=None,
                completion_tokens=None,
            )

        ws = orchestrator.create_workspace(workspace_config)
        agent = make_mock_agent("Alpha")
        agent.run = AsyncMock(return_value=_make_result("response"))
        ws.add_agent(agent)
        result = await orchestrator.delegate("Do something")
        agent.run.assert_called_once_with("Do something", session=None)
        assert result == "response"

    async def test_delegate_to_named_agent(self, orchestrator, workspace_config) -> None:
        from unittest.mock import AsyncMock

        def _r(name: str, content: str) -> AgentRunResult:
            return AgentRunResult(
                content=content,
                agent_used=name,
                provider=None,
                model=None,
                prompt_tokens=None,
                completion_tokens=None,
            )

        ws = orchestrator.create_workspace(workspace_config)
        agent_a = make_mock_agent("Alpha")
        agent_b = make_mock_agent("Beta")
        agent_a.run = AsyncMock(return_value=_r("Alpha", "from alpha"))
        agent_b.run = AsyncMock(return_value=_r("Beta", "from beta"))
        ws.add_agent(agent_a)
        ws.add_agent(agent_b)
        await orchestrator.delegate("task", agent_name="Beta")
        agent_b.run.assert_called_once()
        agent_a.run.assert_not_called()

    async def test_delegate_to_named_workspace(self, orchestrator) -> None:
        from unittest.mock import AsyncMock

        def _r(content: str) -> AgentRunResult:
            return AgentRunResult(
                content=content,
                agent_used="Bot",
                provider=None,
                model=None,
                prompt_tokens=None,
                completion_tokens=None,
            )

        orchestrator.create_workspace(WorkspaceConfig(name="ws1", description=""))
        ws2 = orchestrator.create_workspace(WorkspaceConfig(name="ws2", description=""))
        agent = make_mock_agent("Bot")
        agent.run = AsyncMock(return_value=_r("from ws2"))
        ws2.add_agent(agent)
        await orchestrator.delegate("task", workspace_name="ws2")
        agent.run.assert_called_once_with("task", session=None)

    async def test_delegate_no_active_workspace_raises(self, orchestrator) -> None:
        with pytest.raises(RuntimeError, match="No active workspace"):
            await orchestrator.delegate("task")

    async def test_delegate_no_agents_raises(self, orchestrator, workspace_config) -> None:
        orchestrator.create_workspace(workspace_config)
        with pytest.raises(RuntimeError, match="No agents"):
            await orchestrator.delegate("task")

    async def test_delegate_nonexistent_agent_raises(self, orchestrator, workspace_config) -> None:
        ws = orchestrator.create_workspace(workspace_config)
        ws.add_agent(make_mock_agent("Real"))
        with pytest.raises(ValueError, match="Ghost"):
            await orchestrator.delegate("task", agent_name="Ghost")


class TestAgentHelpers:
    def test_create_agent_adds_to_active_workspace(self, orchestrator, workspace_config) -> None:
        orchestrator.create_workspace(workspace_config)
        config = AgentConfig(name="NewBot", description="", system_prompt="Be helpful.")
        mock = make_mock_graph()
        with patch("personal_assistant.core.agent.create_agent", return_value=mock):
            orchestrator.create_agent(config)
        assert "NewBot" in orchestrator.active_workspace.list_agents()

    def test_replace_agent_replaces_in_active_workspace(
        self, orchestrator, workspace_config
    ) -> None:
        orchestrator.create_workspace(workspace_config)
        old_agent = make_mock_agent("Bot")
        orchestrator.active_workspace.add_agent(old_agent)
        config = AgentConfig(name="Bot", description="", system_prompt="New prompt.")
        mock = make_mock_graph()
        with patch("personal_assistant.core.agent.create_agent", return_value=mock):
            orchestrator.replace_agent(config)
        # A new Agent instance replaced the mock — verify it's no longer the old mock
        assert orchestrator.active_workspace.get_agent("Bot") is not old_agent

    def test_create_agent_no_workspace_raises(self, orchestrator) -> None:
        config = AgentConfig(name="Bot", description="", system_prompt="")
        with pytest.raises(RuntimeError, match="No active workspace"):
            orchestrator.create_agent(config)


class TestUnmanagedAgent:
    def test_create_unmanaged_agent_returns_agent(self, orchestrator) -> None:
        """Test that create_unmanaged_agent returns an Agent instance."""
        config = AgentConfig(name="StandaloneBot", description="", system_prompt="Be helpful.")
        mock = make_mock_graph()
        with patch("personal_assistant.core.agent.create_agent", return_value=mock):
            agent = orchestrator.create_unmanaged_agent(config)
        assert agent is not None
        assert agent.config.name == "StandaloneBot"

    def test_create_unmanaged_agent_not_in_workspace(self, orchestrator, workspace_config) -> None:
        """Test that unmanaged agent is not added to any workspace."""
        orchestrator.create_workspace(workspace_config)
        config = AgentConfig(name="LonelyBot", description="", system_prompt="Be helpful.")
        mock = make_mock_graph()
        with patch("personal_assistant.core.agent.create_agent", return_value=mock):
            orchestrator.create_unmanaged_agent(config)
        # Agent should exist but not be in the active workspace
        assert orchestrator.active_workspace is not None
        assert "LonelyBot" not in orchestrator.active_workspace.list_agents()

    def test_create_unmanaged_agent_no_workspace_required(self, orchestrator) -> None:
        """Test that unmanaged agent can be created without any workspace."""
        config = AgentConfig(name="IndependentBot", description="", system_prompt="Be helpful.")
        mock = make_mock_graph()
        with patch("personal_assistant.core.agent.create_agent", return_value=mock):
            agent = orchestrator.create_unmanaged_agent(config)
        assert agent is not None
        # No active workspace should exist
        assert orchestrator._active_workspace is None

    def test_create_unmanaged_agent_uses_registry(self, orchestrator) -> None:
        """Test that unmanaged agent uses the orchestrator's registry."""
        config = AgentConfig(name="RegistryBot", description="", system_prompt="Be helpful.")
        mock = make_mock_graph()
        with patch("personal_assistant.core.agent.create_agent", return_value=mock):
            agent = orchestrator.create_unmanaged_agent(config)
        # Agent should have access to the registry
        assert agent._registry is orchestrator.registry
