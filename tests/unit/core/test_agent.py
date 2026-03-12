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


class TestAgentFactoryMethods:
    """Tests for Agent factory methods."""

    def test_from_config_creates_agent(self, agent_config, mock_registry, mock_graph):
        """Test that from_config creates an agent with registry."""
        with patch("personal_assistant.core.agent.create_react_agent", return_value=mock_graph):
            agent = Agent.from_config(agent_config, mock_registry)
        assert agent.config == agent_config
        assert agent._registry == mock_registry

    def test_from_llm_creates_agent(self, agent_config, mock_graph):
        """Test that from_llm creates an agent with direct LLM."""
        from langchain_core.language_models import BaseChatModel

        mock_llm = MagicMock(spec=BaseChatModel)
        with patch("personal_assistant.core.agent.create_react_agent", return_value=mock_graph):
            agent = Agent.from_llm(agent_config, mock_llm)
        assert agent.config == agent_config
        assert agent._llm == mock_llm
        assert agent._registry is None


class TestAgentConstructorValidation:
    """Tests for Agent constructor validation."""

    def test_requires_registry_or_llm(self, agent_config):
        """Test that Agent requires either registry or llm."""
        import pytest
        with pytest.raises(ValueError, match="Either 'registry' or 'llm' must be provided"):
            Agent(agent_config)

    def test_accepts_registry(self, agent_config, mock_registry, mock_graph):
        """Test that Agent accepts registry parameter."""
        with patch("personal_assistant.core.agent.create_react_agent", return_value=mock_graph):
            agent = Agent(agent_config, registry=mock_registry)
        assert agent._registry == mock_registry

    def test_accepts_llm(self, agent_config, mock_graph):
        """Test that Agent accepts llm parameter."""
        from langchain_core.language_models import BaseChatModel

        mock_llm = MagicMock(spec=BaseChatModel)
        with patch("personal_assistant.core.agent.create_react_agent", return_value=mock_graph):
            agent = Agent(agent_config, llm=mock_llm)
        assert agent._llm == mock_llm


class TestDeferredGraphRebuild:
    """Tests for deferred graph rebuild behavior."""

    def test_register_tool_sets_dirty_flag(self, agent):
        """Test that register_tool sets the dirty flag."""
        tool = make_tool("new_tool")
        agent._dirty = False
        agent.register_tool(tool)
        assert agent._dirty is True

    def test_remove_tool_sets_dirty_flag(self, agent):
        """Test that remove_tool sets the dirty flag."""
        tool = make_tool("existing")
        agent._tools.append(tool)
        agent._dirty = False
        agent.remove_tool("existing")
        assert agent._dirty is True

    def test_ensure_graph_rebuilds_when_dirty(self, agent, mock_graph):
        """Test that _ensure_graph rebuilds graph when dirty."""
        agent._dirty = True
        new_graph = MagicMock()
        with patch("personal_assistant.core.agent.create_react_agent", return_value=new_graph):
            agent._ensure_graph()
        assert agent._graph == new_graph
        assert agent._dirty is False

    def test_ensure_graph_skips_when_clean(self, agent, mock_graph):
        """Test that _ensure_graph skips rebuild when not dirty."""
        original_graph = agent._graph
        agent._dirty = False
        agent._ensure_graph()
        assert agent._graph is original_graph


class TestBatchTools:
    """Tests for batch_tools context manager."""

    def test_batch_tools_defers_rebuild(self, agent, mock_graph):
        """Test that batch_tools defers graph rebuild until exit."""
        tool1 = make_tool("tool1")
        tool2 = make_tool("tool2")
        new_graph = MagicMock()

        agent._dirty = False
        initial_graph = agent._graph

        with patch("personal_assistant.core.agent.create_react_agent", return_value=new_graph):
            with agent.batch_tools():
                agent.register_tool(tool1)
                agent.register_tool(tool2)
                # Graph should not be rebuilt yet
                assert agent._dirty is True
                assert agent._graph is initial_graph

            # After exiting context, graph should be rebuilt once
            assert agent._graph == new_graph
            assert agent._dirty is False

    def test_batch_tools_with_single_tool(self, agent, mock_graph):
        """Test batch_tools with a single tool addition."""
        tool = make_tool("single_tool")
        new_graph = MagicMock()

        with patch("personal_assistant.core.agent.create_react_agent", return_value=new_graph):
            with agent.batch_tools():
                agent.register_tool(tool)

        assert any(t.name == "single_tool" for t in agent._tools)
        assert agent._dirty is False
