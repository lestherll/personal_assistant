from personal_assistant.core.agent import AgentConfig
from personal_assistant.tools.example_tool import AgentInformationTool, EchoTool


class TestEchoTool:
    def test_run_returns_input(self) -> None:
        tool = EchoTool()
        assert tool._run(message="hello") == "hello"

    def test_run_returns_empty_string(self) -> None:
        tool = EchoTool()
        assert tool._run(message="") == ""


class TestAgentInformationTool:
    def test_run_returns_error_when_config_not_injected(self) -> None:
        tool = AgentInformationTool()
        result = tool._run()
        assert "Error" in result

    def test_run_returns_agent_name_and_description(self) -> None:
        config = AgentConfig(name="MyAgent", description="Does things", system_prompt="...")
        tool = AgentInformationTool(agent_config=config)
        result = tool._run()
        assert "MyAgent" in result
        assert "Does things" in result

    def test_agent_config_not_in_args_schema(self) -> None:
        # agent_config is a tool-level field, not an LLM-facing argument
        tool = AgentInformationTool()
        assert "agent_config" not in tool.args_schema.model_fields
        assert "agent_config" in type(tool).model_fields

    def test_model_copy_creates_independent_instance(self) -> None:
        config_a = AgentConfig(name="A", description="Agent A", system_prompt="...")
        config_b = AgentConfig(name="B", description="Agent B", system_prompt="...")
        tool = AgentInformationTool()
        copy_a = tool.model_copy(update={"agent_config": config_a})
        copy_b = tool.model_copy(update={"agent_config": config_b})
        assert tool.agent_config is None
        assert copy_a.agent_config is not None
        assert copy_b.agent_config is not None
        assert copy_a.agent_config.name == "A"
        assert copy_b.agent_config.name == "B"
