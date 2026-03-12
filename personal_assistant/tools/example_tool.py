from __future__ import annotations

from pydantic import BaseModel, Field

from personal_assistant.core.agent import AgentConfig
from personal_assistant.core.tool import AssistantTool


class EchoInput(BaseModel):
    message: str = Field(description="The message to echo back.")


class EchoTool(AssistantTool[str]):
    """Example tool — echoes the user's message back unchanged.

    Use this as a template when creating new tools:
    1. Define an `args_schema` Pydantic model for typed inputs.
    2. Set `name` and `description` so the agent knows when to use it.
    3. Implement `_run` with the actual logic.
    """

    name: str = "echo"
    description: str = (
        "Echoes the provided message back unchanged. "
        "Useful for testing that tool calls are wired up correctly."
    )
    args_schema: type[BaseModel] = EchoInput

    def _run(self, message: str) -> str:
        return message


class AgentInformationTool(AssistantTool[str]):
    """
    Example tool that returns an agent's AgentConfig info as a string.
    Useful for testing access to agent state within tools.
    """

    name: str = "agent_info"
    description: str = "Returns the agent's name and description as a string."
    args_schema: type[BaseModel] = BaseModel  # No arguments needed
    agent_config: AgentConfig | None = None  # Injected by Agent.register_tool

    def _run(self) -> str:
        agent_info_template = "Agent Name: {name}\nDescription: {description}"
        agent_info = (
            "Error: agent_config was not injected."
            if self.agent_config is None
            else agent_info_template.format(
                name=self.agent_config.name,
                description=self.agent_config.description
            )
        )
        print(f"AgentInformationTool._run called. Returning agent info:\n{agent_info}")
        return agent_info
