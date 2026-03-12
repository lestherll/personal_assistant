from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import BaseTool

from personal_assistant.core.agent import Agent


@dataclass
class WorkspaceConfig:
    name: str
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)


class Workspace:
    """A named container that groups Agents and Tools together.

    Tools added to a workspace are automatically registered with all
    compatible agents already present (and vice-versa when a new agent
    is added).
    """

    def __init__(self, config: WorkspaceConfig) -> None:
        self.config = config
        self._agents: dict[str, Agent] = {}
        self._tools: dict[str, BaseTool] = {}

    # ------------------------------------------------------------------
    # Agent management
    # ------------------------------------------------------------------

    def add_agent(self, agent: Agent) -> None:
        """Add an agent and give it all tools currently in the workspace."""
        for tool in self._tools.values():
            agent.register_tool(tool)
        self._agents[agent.config.name] = agent

    def remove_agent(self, name: str) -> None:
        self._agents.pop(name, None)

    def replace_agent(self, agent: Agent) -> None:
        """Swap out an existing agent (matched by name) with a new one.
        The new agent inherits all current workspace tools."""
        self._agents.pop(agent.config.name, None)
        self.add_agent(agent)

    def get_agent(self, name: str) -> Agent | None:
        return self._agents.get(name)

    def list_agents(self) -> list[str]:
        return list(self._agents.keys())

    # ------------------------------------------------------------------
    # Tool management
    # ------------------------------------------------------------------

    def add_tool(self, tool: BaseTool) -> None:
        """Add a tool and register it with all agents in the workspace."""
        self._tools[tool.name] = tool
        for agent in self._agents.values():
            agent.register_tool(tool)

    def remove_tool(self, name: str) -> None:
        """Remove a tool from the workspace and from all agents."""
        self._tools.pop(name, None)
        for agent in self._agents.values():
            agent.remove_tool(name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    # ------------------------------------------------------------------
    # Selective tool assignment (agent-specific tools)
    # ------------------------------------------------------------------

    def add_tool_to_agent(self, agent_name: str, tool: BaseTool) -> None:
        """Add a tool to a specific agent only (not to all workspace agents).

        Args:
            agent_name: Name of the agent to add the tool to.
            tool: The tool to add.

        Raises:
            KeyError: If no agent with the given name exists.
        """
        agent = self._agents.get(agent_name)
        if agent is None:
            raise KeyError(f"No agent named '{agent_name}' in workspace")
        agent.register_tool(tool)

    def remove_tool_from_agent(self, agent_name: str, tool_name: str) -> None:
        """Remove a tool from a specific agent only.

        Args:
            agent_name: Name of the agent to remove the tool from.
            tool_name: Name of the tool to remove.

        Raises:
            KeyError: If no agent with the given name exists.
        """
        agent = self._agents.get(agent_name)
        if agent is None:
            raise KeyError(f"No agent named '{agent_name}' in workspace")
        agent.remove_tool(tool_name)

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"Workspace(name={self.config.name!r}, "
            f"agents={self.list_agents()}, "
            f"tools={self.list_tools()})"
        )
