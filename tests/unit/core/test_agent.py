from unittest.mock import MagicMock, patch

from langchain_core.tools import BaseTool

from personal_assistant.core.agent import Agent, AgentConfig
from personal_assistant.tools.example_tool import AgentInformationTool


def make_tool(name: str = "test_tool") -> BaseTool:
    tool = MagicMock(spec=BaseTool)
    tool.name = name
    return tool


class TestAgentCreation:
    def test_agent_resolves_llm_from_registry(
        self, agent_config, mock_registry, mock_provider, mock_graph
    ) -> None:
        with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
            agent = Agent(agent_config, mock_registry)
            assert agent.get_llm_info()["source"] == "registry"

        mock_provider.get_model.assert_called_with(agent_config.model)

    def test_agent_starts_with_empty_history(self, agent) -> None:
        assert agent.history == []

    def test_agent_starts_with_no_tools(self, agent) -> None:
        assert agent.tools == []


class TestToolManagement:
    def test_register_tool(self, agent, mock_graph) -> None:
        tool = make_tool("weather")
        with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
            agent.register_tool(tool)
        assert "weather" in agent.tools

    def test_register_duplicate_tool_ignored(self, agent, mock_graph) -> None:
        tool = make_tool("weather")
        with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
            agent.register_tool(tool)
            agent.register_tool(tool)
        assert agent.tools.count("weather") == 1

    def test_remove_tool(self, agent, mock_graph) -> None:
        tool = make_tool("weather")
        with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
            agent.register_tool(tool)
            agent.remove_tool("weather")
        assert "weather" not in agent.tools

    def test_allowed_tools_filters_registration(self, mock_registry, mock_graph) -> None:
        config = AgentConfig(
            name="Restricted",
            description="Restricted agent",
            system_prompt="You are restricted.",
            allowed_tools=["allowed_tool"],
        )
        with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
            agent = Agent(config, mock_registry)
            agent.register_tool(make_tool("allowed_tool"))
            agent.register_tool(make_tool("blocked_tool"))
        assert "allowed_tool" in agent.tools
        assert "blocked_tool" not in agent.tools

    def test_empty_allowed_tools_accepts_all(self, agent, mock_graph) -> None:
        with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
            agent.register_tool(make_tool("tool_a"))
            agent.register_tool(make_tool("tool_b"))
        assert "tool_a" in agent.tools
        assert "tool_b" in agent.tools

    def test_register_tool_injects_agent_config(self, agent, mock_graph) -> None:
        tool = AgentInformationTool()
        with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
            agent.register_tool(tool)
        registered = next(t for t in agent._tools if t.name == "agent_info")
        assert registered.agent_config == agent.config

    def test_register_tool_does_not_mutate_original(self, agent, mock_graph) -> None:
        tool = AgentInformationTool()
        with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
            agent.register_tool(tool)
        assert tool.agent_config is None

    def test_register_tool_different_agents_get_separate_copies(
        self, agent_config, mock_registry, mock_graph
    ) -> None:
        tool = AgentInformationTool()
        config_b = AgentConfig(name="AgentB", description="Agent B", system_prompt="You are B.")
        with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
            agent_a = Agent(agent_config, mock_registry)
            agent_b = Agent(config_b, mock_registry)
            agent_a.register_tool(tool)
            agent_b.register_tool(tool)
        tool_a = next(t for t in agent_a._tools if t.name == "agent_info")
        tool_b = next(t for t in agent_b._tools if t.name == "agent_info")
        assert tool_a is not tool_b
        assert tool_a.agent_config is not None
        assert tool_b.agent_config is not None
        assert tool_a.agent_config.name == agent_config.name
        assert tool_b.agent_config.name == "AgentB"


class TestRunAndHistory:
    async def test_run_returns_last_message_content(self, agent) -> None:
        result = await agent.run("Hello")
        assert result.content == "Test response"
        assert result.agent_used == "TestAgent"

    async def test_run_appends_to_history(self, agent) -> None:
        await agent.run("Hello")
        assert len(agent.history) > 0

    async def test_run_accumulates_history_across_turns(self, agent) -> None:
        await agent.run("First message")
        first_len = len(agent.history)
        await agent.run("Second message")
        assert len(agent.history) > first_len

    async def test_run_passes_full_history_to_graph(self, agent) -> None:
        await agent.run("First message")
        await agent.run("Second message")
        # Second invoke should receive more messages than the first
        first_call_msgs = agent._graph.ainvoke.call_args_list[0][0][0]["messages"]
        second_call_msgs = agent._graph.ainvoke.call_args_list[1][0][0]["messages"]
        assert len(second_call_msgs) > len(first_call_msgs)


class TestReset:
    async def test_reset_clears_history(self, agent) -> None:
        await agent.run("Hello")
        agent.reset()
        assert agent.history == []

    async def test_run_after_reset_starts_fresh(self, agent) -> None:
        await agent.run("Hello")
        agent.reset()
        await agent.run("Hello again")
        # After reset, graph should receive only 1 message (not accumulated)
        last_call_msgs = agent._graph.ainvoke.call_args_list[-1][0][0]["messages"]
        assert len(last_call_msgs) == 1


class TestStream:
    async def test_stream_yields_messages(self, agent) -> None:
        messages = [msg async for msg in agent.stream("Hello")]
        assert len(messages) > 0

    async def test_stream_updates_history(self, agent) -> None:
        async for _ in agent.stream("Hello"):
            pass
        assert len(agent.history) > 0


class TestAgentFactoryMethods:
    """Tests for Agent factory methods."""

    def test_from_config_creates_agent(self, agent_config, mock_registry, mock_graph) -> None:
        """Test that from_config creates an agent with registry."""
        with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
            agent = Agent.from_config(agent_config, mock_registry)
        assert agent.config == agent_config
        assert agent._registry == mock_registry

    def test_from_llm_creates_agent(self, agent_config, mock_graph) -> None:
        """Test that from_llm creates an agent with direct LLM."""
        from langchain_core.language_models import BaseChatModel

        mock_llm = MagicMock(spec=BaseChatModel)
        with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
            agent = Agent.from_llm(agent_config, mock_llm)
        assert agent.config == agent_config
        assert agent._llm == mock_llm
        assert agent._registry is None


class TestAgentConstructorValidation:
    """Tests for Agent constructor validation."""

    def test_requires_registry_or_llm(self, agent_config) -> None:
        """Test that Agent requires either registry or llm."""
        import pytest

        with pytest.raises(
            ValueError, match="Invalid combination of 'registry' and 'llm' arguments"
        ):
            Agent(agent_config)

    def test_accepts_registry(self, agent_config, mock_registry, mock_graph) -> None:
        """Test that Agent accepts registry parameter."""
        with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
            agent = Agent(agent_config, registry=mock_registry)
        assert agent._registry == mock_registry

    def test_accepts_llm(self, agent_config, mock_graph) -> None:
        """Test that Agent accepts llm parameter."""
        from langchain_core.language_models import BaseChatModel

        mock_llm = MagicMock(spec=BaseChatModel)
        with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
            agent = Agent(agent_config, llm=mock_llm)
        assert agent._llm == mock_llm


class TestDeferredGraphRebuild:
    """Tests for deferred graph rebuild behavior."""

    def test_register_tool_sets_dirty_flag(self, agent) -> None:
        """Test that register_tool sets the dirty flag."""
        tool = make_tool("new_tool")
        agent._dirty = False
        agent.register_tool(tool)
        assert agent._dirty is True

    def test_remove_tool_sets_dirty_flag(self, agent) -> None:
        """Test that remove_tool sets the dirty flag."""
        tool = make_tool("existing")
        agent._tools.append(tool)
        agent._dirty = False
        agent.remove_tool("existing")
        assert agent._dirty is True

    def test_ensure_graph_rebuilds_when_dirty(self, agent, mock_graph) -> None:
        """Test that _ensure_graph rebuilds graph when dirty."""
        agent._dirty = True
        new_graph = MagicMock()
        with patch("personal_assistant.core.agent.create_agent", return_value=new_graph):
            agent._ensure_graph()
        assert agent._graph == new_graph
        assert agent._dirty is False

    def test_ensure_graph_skips_when_clean(self, agent, mock_graph) -> None:
        """Test that _ensure_graph skips rebuild when not dirty."""
        original_graph = agent._graph
        agent._dirty = False
        agent._ensure_graph()
        assert agent._graph is original_graph


class TestGetLlmInfo:
    """Tests for Agent.get_llm_info()."""

    def test_registry_path_returns_config_values(
        self, agent_config, mock_registry, mock_graph
    ) -> None:
        with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
            agent = Agent(agent_config, mock_registry)
        info = agent.get_llm_info()
        assert info["source"] == "registry"
        assert info["provider"] == agent_config.provider
        assert info["model"] == agent_config.model

    def test_direct_llm_path_returns_class_name(self, agent_config, mock_graph) -> None:
        from langchain_core.language_models import BaseChatModel

        mock_llm = MagicMock(spec=BaseChatModel)
        mock_llm.model = "test-model"
        with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
            agent = Agent.from_llm(agent_config, mock_llm)
        info = agent.get_llm_info()
        assert info["source"] == "direct"
        assert info["provider"] == type(mock_llm).__name__
        assert info["model"] == "test-model"


class TestSetLlm:
    """Tests for Agent.set_llm()."""

    def test_set_llm_replaces_llm(self, agent_config, mock_registry, mock_graph) -> None:
        from langchain_core.language_models import BaseChatModel

        with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
            agent = Agent(agent_config, mock_registry)
            new_llm = MagicMock(spec=BaseChatModel)
            agent.set_llm(new_llm)
        assert agent._llm is new_llm

    def test_set_llm_clears_registry(self, agent_config, mock_registry, mock_graph) -> None:
        from langchain_core.language_models import BaseChatModel

        with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
            agent = Agent(agent_config, mock_registry)
            agent.set_llm(MagicMock(spec=BaseChatModel))
        assert agent._registry is None

    def test_set_llm_rebuilds_graph(self, agent_config, mock_registry, mock_graph) -> None:
        from langchain_core.language_models import BaseChatModel

        with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
            agent = Agent(agent_config, mock_registry)
            original_graph = agent._graph
            new_graph = MagicMock()
            with patch("personal_assistant.core.agent.create_agent", return_value=new_graph):
                agent.set_llm(MagicMock(spec=BaseChatModel))
        assert agent._graph is new_graph
        assert agent._graph is not original_graph


class TestBatchTools:
    """Tests for batch_tools context manager."""

    def test_batch_tools_defers_rebuild(self, agent, mock_graph) -> None:
        """Test that batch_tools defers graph rebuild until exit."""
        tool1 = make_tool("tool1")
        tool2 = make_tool("tool2")
        new_graph = MagicMock()

        agent._dirty = False
        initial_graph = agent._graph

        with patch("personal_assistant.core.agent.create_agent", return_value=new_graph):
            with agent.batch_tools():
                agent.register_tool(tool1)
                agent.register_tool(tool2)
                # Graph should not be rebuilt yet
                assert agent._dirty is True
                assert agent._graph is initial_graph

            # After exiting context, graph should be rebuilt once
            assert agent._graph == new_graph
            assert agent._dirty is False

    def test_batch_tools_with_single_tool(self, agent, mock_graph) -> None:
        """Test batch_tools with a single tool addition."""
        tool = make_tool("single_tool")
        new_graph = MagicMock()

        with patch("personal_assistant.core.agent.create_agent", return_value=new_graph):
            with agent.batch_tools():
                agent.register_tool(tool)

        assert any(t.name == "single_tool" for t in agent._tools)
        assert agent._dirty is False


class TestClone:
    """Tests for Agent.clone()."""

    def test_clone_returns_new_instance(self, agent) -> None:
        clone = agent.clone()
        assert clone is not agent

    def test_clone_has_same_config(self, agent) -> None:
        clone = agent.clone()
        assert clone.config is agent.config

    def test_clone_has_same_llm(self, agent) -> None:
        clone = agent.clone()
        assert clone._llm is agent._llm

    def test_clone_has_same_tools(self, agent, mock_graph) -> None:
        tool = make_tool("weather")
        with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
            agent.register_tool(tool)
            clone = agent.clone()
        assert clone.tools == agent.tools

    def test_clone_has_empty_history(self, agent) -> None:
        """Clone starts with empty history regardless of template state."""
        from unittest.mock import MagicMock as MM

        agent._history.append(MM())
        clone = agent.clone()
        assert clone.history == []

    def test_clone_has_no_conversation_id(self, agent) -> None:
        from unittest.mock import MagicMock as MM

        agent._conversation_id = MM()
        clone = agent.clone()
        assert clone.conversation_id is None

    async def test_clone_history_is_independent(self, agent) -> None:
        clone = agent.clone()
        await agent.run("Hello")
        assert clone.history == []

    def test_clone_of_clone_is_independent(self, agent) -> None:
        clone1 = agent.clone()
        clone2 = agent.clone()
        assert clone1 is not clone2

    def test_clone_with_llm_override_uses_new_llm(self, agent) -> None:
        from langchain_core.language_models import BaseChatModel

        override_llm = MagicMock(spec=BaseChatModel)
        clone = agent.clone(llm=override_llm)
        assert clone._llm is override_llm

    def test_clone_with_llm_override_does_not_affect_template(self, agent) -> None:
        from langchain_core.language_models import BaseChatModel

        original_llm = agent._llm
        override_llm = MagicMock(spec=BaseChatModel)
        agent.clone(llm=override_llm)
        assert agent._llm is original_llm

    def test_clone_without_llm_uses_template_llm(self, agent) -> None:
        clone = agent.clone()
        assert clone._llm is agent._llm
