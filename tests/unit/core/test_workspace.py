from unittest.mock import MagicMock

import pytest
from langchain_core.tools import BaseTool

from personal_assistant.core.agent import Agent, AgentConfig
from personal_assistant.core.workspace import Workspace, WorkspaceConfig


def make_mock_agent(name: str = "TestAgent") -> Agent:
    agent = MagicMock(spec=Agent)
    agent.config = AgentConfig(
        name=name,
        description="A mock agent",
        system_prompt="You are a mock.",
    )
    agent.config.allowed_tools = []
    return agent


def make_mock_tool(name: str = "test_tool") -> BaseTool:
    tool = MagicMock(spec=BaseTool)
    tool.name = name
    return tool


@pytest.fixture
def workspace() -> Workspace:
    return Workspace(WorkspaceConfig(name="test", description="Test workspace"))


class TestAgentManagement:
    def test_add_agent(self, workspace):
        agent = make_mock_agent()
        workspace.add_agent(agent)
        assert "TestAgent" in workspace.list_agents()

    def test_remove_agent(self, workspace):
        agent = make_mock_agent()
        workspace.add_agent(agent)
        workspace.remove_agent("TestAgent")
        assert "TestAgent" not in workspace.list_agents()

    def test_remove_nonexistent_agent_is_safe(self, workspace):
        workspace.remove_agent("NonExistent")  # should not raise

    def test_get_agent_returns_correct_agent(self, workspace):
        agent = make_mock_agent("Alpha")
        workspace.add_agent(agent)
        assert workspace.get_agent("Alpha") is agent

    def test_get_nonexistent_agent_returns_none(self, workspace):
        assert workspace.get_agent("Ghost") is None

    def test_list_agents(self, workspace):
        workspace.add_agent(make_mock_agent("A"))
        workspace.add_agent(make_mock_agent("B"))
        assert workspace.list_agents() == ["A", "B"]

    def test_replace_agent_swaps_by_name(self, workspace):
        old_agent = make_mock_agent("Bot")
        new_agent = make_mock_agent("Bot")
        workspace.add_agent(old_agent)
        workspace.replace_agent(new_agent)
        assert workspace.get_agent("Bot") is new_agent
        assert workspace.list_agents().count("Bot") == 1

    def test_add_agent_registers_existing_tools(self, workspace):
        tool = make_mock_tool("search")
        workspace.add_tool(tool)
        agent = make_mock_agent()
        workspace.add_agent(agent)
        agent.register_tool.assert_called_with(tool)


class TestToolManagement:
    def test_add_tool(self, workspace):
        tool = make_mock_tool("search")
        workspace.add_tool(tool)
        assert "search" in workspace.list_tools()

    def test_remove_tool(self, workspace):
        tool = make_mock_tool("search")
        workspace.add_tool(tool)
        workspace.remove_tool("search")
        assert "search" not in workspace.list_tools()

    def test_remove_nonexistent_tool_is_safe(self, workspace):
        workspace.remove_tool("ghost")  # should not raise

    def test_add_tool_registers_with_existing_agents(self, workspace):
        agent = make_mock_agent()
        workspace.add_agent(agent)
        tool = make_mock_tool("search")
        workspace.add_tool(tool)
        agent.register_tool.assert_called_with(tool)

    def test_remove_tool_removes_from_all_agents(self, workspace):
        agent = make_mock_agent()
        workspace.add_agent(agent)
        tool = make_mock_tool("search")
        workspace.add_tool(tool)
        workspace.remove_tool("search")
        agent.remove_tool.assert_called_with("search")

    def test_list_tools(self, workspace):
        workspace.add_tool(make_mock_tool("a"))
        workspace.add_tool(make_mock_tool("b"))
        assert workspace.list_tools() == ["a", "b"]


class TestSelectiveToolAssignment:
    def test_add_tool_to_agent_specific_agent_only(self, workspace):
        """Test that add_tool_to_agent only adds to the specified agent."""
        agent_a = make_mock_agent("AgentA")
        agent_b = make_mock_agent("AgentB")
        workspace.add_agent(agent_a)
        workspace.add_agent(agent_b)

        tool = make_mock_tool("special_tool")
        workspace.add_tool_to_agent("AgentA", tool)

        # AgentA should have the tool registered
        agent_a.register_tool.assert_called_with(tool)
        # AgentB should NOT have been called with this tool
        agent_b.register_tool.assert_not_called()

    def test_add_tool_to_agent_nonexistent_raises(self, workspace):
        """Test that add_tool_to_agent raises for nonexistent agent."""
        tool = make_mock_tool("tool")
        with pytest.raises(KeyError, match="No agent named 'Ghost'"):
            workspace.add_tool_to_agent("Ghost", tool)

    def test_remove_tool_from_agent_specific_agent_only(self, workspace):
        """Test that remove_tool_from_agent only removes from specified agent."""
        agent_a = make_mock_agent("AgentA")
        agent_b = make_mock_agent("AgentB")
        workspace.add_agent(agent_a)
        workspace.add_agent(agent_b)

        # First add a tool to both agents via workspace
        tool = make_mock_tool("shared_tool")
        workspace.add_tool(tool)

        # Reset mock call counts
        agent_a.reset_mock()
        agent_b.reset_mock()

        # Now remove from AgentA only
        workspace.remove_tool_from_agent("AgentA", "shared_tool")

        # AgentA should have the tool removed
        agent_a.remove_tool.assert_called_with("shared_tool")
        # AgentB should NOT have been called
        agent_b.remove_tool.assert_not_called()

    def test_remove_tool_from_agent_nonexistent_raises(self, workspace):
        """Test that remove_tool_from_agent raises for nonexistent agent."""
        with pytest.raises(KeyError, match="No agent named 'Ghost'"):
            workspace.remove_tool_from_agent("Ghost", "tool")

    def test_selective_tool_does_not_affect_workspace_tools(self, workspace):
        """Test that selective tool assignment doesn't add to workspace tools."""
        agent = make_mock_agent("Agent")
        workspace.add_agent(agent)

        tool = make_mock_tool("private_tool")
        workspace.add_tool_to_agent("Agent", tool)

        # Tool should NOT be in workspace tools
        assert "private_tool" not in workspace.list_tools()
