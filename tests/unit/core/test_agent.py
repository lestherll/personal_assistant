from unittest.mock import MagicMock, patch

from langchain_core.tools import BaseTool

from personal_assistant.core.agent import Agent, AgentConfig


def make_tool(name: str = "test_tool") -> BaseTool:
    tool = MagicMock(spec=BaseTool)
    tool.name = name
    return tool


class TestAgentCreation:
    def test_agent_resolves_llm_from_registry(self, agent_config, mock_graph):
        registry = MagicMock()
        registry.get.return_value.get_model.return_value = MagicMock()
        with patch("personal_assistant.core.agent.create_react_agent", return_value=mock_graph):
            Agent(agent_config, registry)
        registry.get.assert_called_with(agent_config.provider)

    def test_agent_starts_with_empty_history(self, agent):
        assert agent.history == []

    def test_agent_starts_with_no_tools(self, agent):
        assert agent.tools == []


class TestToolManagement:
    def test_register_tool(self, agent, mock_graph):
        tool = make_tool("weather")
        with patch("personal_assistant.core.agent.create_react_agent", return_value=mock_graph):
            agent.register_tool(tool)
        assert "weather" in agent.tools

    def test_register_duplicate_tool_ignored(self, agent, mock_graph):
        tool = make_tool("weather")
        with patch("personal_assistant.core.agent.create_react_agent", return_value=mock_graph):
            agent.register_tool(tool)
            agent.register_tool(tool)
        assert agent.tools.count("weather") == 1

    def test_remove_tool(self, agent, mock_graph):
        tool = make_tool("weather")
        with patch("personal_assistant.core.agent.create_react_agent", return_value=mock_graph):
            agent.register_tool(tool)
            agent.remove_tool("weather")
        assert "weather" not in agent.tools

    def test_allowed_tools_filters_registration(self, mock_registry, mock_graph):
        config = AgentConfig(
            name="Restricted",
            description="Restricted agent",
            system_prompt="You are restricted.",
            allowed_tools=["allowed_tool"],
        )
        with patch("personal_assistant.core.agent.create_react_agent", return_value=mock_graph):
            agent = Agent(config, mock_registry)
            agent.register_tool(make_tool("allowed_tool"))
            agent.register_tool(make_tool("blocked_tool"))
        assert "allowed_tool" in agent.tools
        assert "blocked_tool" not in agent.tools

    def test_empty_allowed_tools_accepts_all(self, agent, mock_graph):
        with patch("personal_assistant.core.agent.create_react_agent", return_value=mock_graph):
            agent.register_tool(make_tool("tool_a"))
            agent.register_tool(make_tool("tool_b"))
        assert "tool_a" in agent.tools
        assert "tool_b" in agent.tools


class TestRunAndHistory:
    def test_run_returns_last_message_content(self, agent):
        response = agent.run("Hello")
        assert response == "Test response"

    def test_run_appends_to_history(self, agent):
        agent.run("Hello")
        assert len(agent.history) > 0

    def test_run_accumulates_history_across_turns(self, agent):
        agent.run("First message")
        first_len = len(agent.history)
        agent.run("Second message")
        assert len(agent.history) > first_len

    def test_run_passes_full_history_to_graph(self, agent):
        agent.run("First message")
        agent.run("Second message")
        # Second invoke should receive more messages than the first
        first_call_msgs = agent._graph.invoke.call_args_list[0][0][0]["messages"]
        second_call_msgs = agent._graph.invoke.call_args_list[1][0][0]["messages"]
        assert len(second_call_msgs) > len(first_call_msgs)


class TestReset:
    def test_reset_clears_history(self, agent):
        agent.run("Hello")
        agent.reset()
        assert agent.history == []

    def test_run_after_reset_starts_fresh(self, agent):
        agent.run("Hello")
        agent.reset()
        agent.run("Hello again")
        # After reset, graph should receive only 1 message (not accumulated)
        last_call_msgs = agent._graph.invoke.call_args_list[-1][0][0]["messages"]
        assert len(last_call_msgs) == 1


class TestStream:
    def test_stream_yields_messages(self, agent):
        messages = list(agent.stream("Hello"))
        assert len(messages) > 0

    def test_stream_updates_history(self, agent):
        list(agent.stream("Hello"))
        assert len(agent.history) > 0
