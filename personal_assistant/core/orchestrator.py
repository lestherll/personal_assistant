from __future__ import annotations

from typing import TYPE_CHECKING

from personal_assistant.core.workspace import Workspace, WorkspaceConfig
from personal_assistant.providers.registry import ProviderRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from personal_assistant.core.agent import Agent, AgentConfig


class Orchestrator:
    """Central coordinator that manages a ProviderRegistry and Workspaces.

    Usage::

        registry = ProviderRegistry()
        registry.register(AnthropicProvider(), default=True)
        registry.register(OllamaProvider())

        orchestrator = Orchestrator(registry)
        workspace = orchestrator.create_workspace(WorkspaceConfig(...))
        workspace.add_agent(MyAgent(config, orchestrator.registry))

        response = orchestrator.delegate("Summarise my emails")
    """

    def __init__(self, registry: ProviderRegistry) -> None:
        self.registry = registry
        self._workspaces: dict[str, Workspace] = {}
        self._active_workspace: str | None = None

    # ------------------------------------------------------------------
    # Workspace management
    # ------------------------------------------------------------------

    def create_workspace(self, config: WorkspaceConfig) -> Workspace:
        workspace = Workspace(config)
        self._workspaces[config.name] = workspace
        if self._active_workspace is None:
            self._active_workspace = config.name
        return workspace

    def add_workspace(self, workspace: Workspace) -> None:
        self._workspaces[workspace.config.name] = workspace
        if self._active_workspace is None:
            self._active_workspace = workspace.config.name

    def get_workspace(self, name: str) -> Workspace | None:
        return self._workspaces.get(name)

    def set_active_workspace(self, name: str) -> None:
        if name not in self._workspaces:
            raise ValueError(f"Workspace '{name}' does not exist.")
        self._active_workspace = name

    @property
    def active_workspace(self) -> Workspace | None:
        if self._active_workspace:
            return self._workspaces.get(self._active_workspace)
        return None

    def list_workspaces(self) -> list[str]:
        return list(self._workspaces.keys())

    def remove_workspace(self, name: str) -> None:
        """Remove a workspace by name. No-op if it does not exist.

        If the removed workspace was the active one, the active workspace is
        reset to the first remaining workspace, or None if none remain.
        """
        self._workspaces.pop(name, None)
        if self._active_workspace == name:
            remaining = list(self._workspaces.keys())
            self._active_workspace = remaining[0] if remaining else None

    # ------------------------------------------------------------------
    # Agent management helpers
    # ------------------------------------------------------------------

    def create_agent(
        self,
        config: AgentConfig,
        workspace_name: str | None = None,
    ) -> Agent:
        """Create an agent from a config and add it to a workspace.

        Args:
            config: AgentConfig describing the agent's name, prompt, provider, etc.
            workspace_name: Target workspace. Defaults to the active one.

        Returns:
            The newly created Agent.
        """
        from personal_assistant.core.agent import Agent

        workspace = self.get_workspace(workspace_name) if workspace_name else self.active_workspace
        if workspace is None:
            raise RuntimeError("No active workspace. Create one first.")
        agent = Agent(config, self.registry)
        workspace.add_agent(agent)
        return agent

    def replace_agent(
        self,
        config: AgentConfig,
        workspace_name: str | None = None,
    ) -> Agent:
        """Replace an existing agent (matched by config.name) with a fresh one.

        Useful for hot-swapping provider, model, or system prompt without
        touching the rest of the workspace.
        """
        from personal_assistant.core.agent import Agent

        workspace = self.get_workspace(workspace_name) if workspace_name else self.active_workspace
        if workspace is None:
            raise RuntimeError("No active workspace.")
        agent = Agent(config, self.registry)
        workspace.replace_agent(agent)
        return agent

    def get_or_create_agent(
        self,
        config: AgentConfig,
        workspace_name: str | None = None,
    ) -> Agent:
        """Return the existing agent with ``config.name``, or create and add it.

        Args:
            config: Config for the agent to look up or create.
            workspace_name: Target workspace. Defaults to the active one.

        Returns:
            The existing or newly created Agent.
        """
        workspace = self.get_workspace(workspace_name) if workspace_name else self.active_workspace
        if workspace is None:
            raise RuntimeError("No active workspace. Create one first.")
        return workspace.get_or_create_agent(config, self.registry)

    def create_unmanaged_agent(self, config: AgentConfig) -> Agent:
        """Create an agent without adding it to any workspace.

        The agent is backed by the orchestrator's registry but is not tracked
        in any workspace. Useful for one-off agents that don't require workspace
        tool propagation or lifecycle management.

        Args:
            config: AgentConfig describing the agent's name, prompt, provider, etc.

        Returns:
            An unmanaged Agent instance.
        """
        from personal_assistant.core.agent import Agent

        return Agent(config, self.registry)

    # ------------------------------------------------------------------
    # Task delegation
    # ------------------------------------------------------------------

    async def delegate(
        self,
        task: str,
        agent_name: str | None = None,
        workspace_name: str | None = None,
        session: AsyncSession | None = None,
    ) -> str:
        """Delegate a task to an agent.

        Args:
            task: The user's request.
            agent_name: Target a specific agent by name. Defaults to the first
                        available agent in the workspace.
            workspace_name: Target a specific workspace. Defaults to the active one.
            session: Optional SQLAlchemy async session for persisting messages.
        """
        workspace = self.get_workspace(workspace_name) if workspace_name else self.active_workspace
        if workspace is None:
            raise RuntimeError("No active workspace. Create one first.")

        match (agent_name, workspace.list_agents()):
            case (None, []):
                raise RuntimeError(f"No agents in workspace '{workspace.config.name}'.")
            case (None, [first, *_]):
                agent = workspace.get_agent(first)
            case (str() as name, _):
                agent = workspace.get_agent(name)
                if agent is None:
                    raise ValueError(
                        f"Agent '{name}' not found in workspace '{workspace.config.name}'."
                    )
            case _:
                raise RuntimeError("No agent found to delegate to.")

        result = await agent.run(task, session=session)
        return result.content

    async def delegate_to_workspace(
        self,
        task: str,
        workspace_name: str | None = None,
        thread_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> tuple[str, str, str]:
        """Delegate a task to the workspace supervisor for automatic routing.

        The supervisor selects the best agent per turn and maintains
        conversation history across turns via LangGraph checkpointing.

        Args:
            task: User message.
            workspace_name: Target workspace. Defaults to the active one.
            thread_id: Conversation thread ID.  Generated if not provided.
            session: Optional DB session (reserved for future persistence).

        Returns:
            Tuple of ``(response_text, thread_id, agent_used)``.
        """
        workspace = self.get_workspace(workspace_name) if workspace_name else self.active_workspace
        if workspace is None:
            raise RuntimeError("No active workspace. Create one first.")
        return await workspace.delegate(task, thread_id=thread_id, session=session)

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"Orchestrator(providers={self.registry.list()}, "
            f"workspaces={self.list_workspaces()}, "
            f"active={self._active_workspace!r})"
        )
