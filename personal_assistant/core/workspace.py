from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from langchain_core.tools import BaseTool

from personal_assistant.core.agent import Agent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from personal_assistant.core.agent import AgentConfig
    from personal_assistant.core.supervisor import WorkspaceSupervisor
    from personal_assistant.providers.registry import ProviderRegistry


@dataclass
class WorkspaceConfig:
    name: str
    description: str
    metadata: dict[str, Any] = field(default_factory=lambda: {})


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
        self._supervisor: WorkspaceSupervisor | None = None

    # ------------------------------------------------------------------
    # Agent management
    # ------------------------------------------------------------------

    def add_agent(self, agent: Agent) -> None:
        """Add an agent and give it all tools currently in the workspace."""
        self._register_agent(agent)
        self._rebuild_supervisor()

    def add_agents(self, agents: list[Agent]) -> None:
        """Add multiple agents, rebuilding the supervisor only once at the end."""
        for agent in agents:
            self._register_agent(agent)
        self._rebuild_supervisor()

    def _register_agent(self, agent: Agent) -> None:
        """Register an agent and propagate workspace tools without rebuilding the supervisor.

        Raises:
            ValueError: If an agent with the same name already exists.
        """
        if agent.config.name in self._agents:
            raise ValueError(f"Agent '{agent.config.name}' already exists in workspace")
        for tool in self._tools.values():
            agent.register_tool(tool)
        self._agents[agent.config.name] = agent

    def remove_agent(self, name: str) -> None:
        if name not in self._agents:
            raise KeyError(f"No agent named '{name}' in workspace")
        del self._agents[name]
        self._rebuild_supervisor()

    def replace_agent(self, agent: Agent) -> None:
        """Swap out an existing agent (matched by name) with a new one.
        The new agent inherits all current workspace tools."""
        self._agents.pop(agent.config.name, None)
        self.add_agent(agent)

    def get_agent(self, name: str) -> Agent | None:
        return self._agents.get(name)

    def get_or_create_agent(self, config: AgentConfig, registry: ProviderRegistry) -> Agent:
        """Return the existing agent with ``config.name``, or create and add one.

        Args:
            config: Config for the agent to look up or create.
            registry: Provider registry used only when creating a new agent.

        Returns:
            The existing or newly created Agent.
        """
        existing = self._agents.get(config.name)
        if existing is not None:
            return existing
        agent = Agent.from_config(config, registry)
        self.add_agent(agent)
        return agent

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
        """Remove a tool from the workspace and from all agents.

        Raises:
            KeyError: If no tool with the given name exists in the workspace.
        """
        if name not in self._tools:
            raise KeyError(f"No tool named '{name}' in workspace")
        del self._tools[name]
        for agent in self._agents.values():
            agent.remove_tool(name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    # ------------------------------------------------------------------
    # Selective tool assignment (agent-specific tools)
    # ------------------------------------------------------------------

    def add_tool_to_agent(self, agent_name: str, tool: BaseTool) -> None:
        """Add a tool to a specific agent only (not to all workspace agents).

        Note: tools added this way are NOT tracked in the workspace tool registry
        and will NOT appear in list_tools(). They are agent-private tools.
        Use add_tool() instead if you want the tool to be shared across all agents.

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
    # Supervisor / workspace-level delegation
    # ------------------------------------------------------------------

    def _rebuild_supervisor(self) -> None:
        """Rebuild (or clear) the WorkspaceSupervisor after agent changes."""
        agents = list(self._agents.values())
        if not agents:
            self._supervisor = None
            return

        from personal_assistant.core.supervisor import WorkspaceSupervisor

        llm = agents[0].llm
        if self._supervisor is None:
            self._supervisor = WorkspaceSupervisor(agents, llm)
        else:
            self._supervisor.rebuild(agents)

    async def delegate(
        self,
        message: str,
        thread_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> tuple[str, str, str]:
        """Delegate a message to the workspace supervisor for automatic routing.

        The supervisor uses an LLM to select the most suitable agent for each
        turn.  Conversation history is maintained across turns via LangGraph's
        checkpointer, keyed by ``thread_id``.

        Args:
            message: User message text.
            thread_id: Conversation thread ID.  A new UUID is generated when
                not provided.
            session: Reserved for future DB-backed checkpointing (unused).

        Returns:
            Tuple of ``(response_text, thread_id, agent_used)``.

        Raises:
            RuntimeError: If the workspace has no agents.
        """
        if not self._agents:
            raise RuntimeError(f"Workspace '{self.config.name}' has no agents to route to.")

        if self._supervisor is None:
            self._rebuild_supervisor()

        if self._supervisor is None:
            raise RuntimeError("Failed to initialize workspace supervisor.")

        return await self._supervisor.run(message, thread_id)

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"Workspace(name={self.config.name!r}, "
            f"agents={self.list_agents()}, "
            f"tools={self.list_tools()})"
        )
