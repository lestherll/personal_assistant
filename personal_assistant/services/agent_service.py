from __future__ import annotations

from collections.abc import AsyncIterator

from personal_assistant.core.agent import Agent, AgentConfig
from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.core.workspace import Workspace
from personal_assistant.services.exceptions import AlreadyExistsError, NotFoundError
from personal_assistant.services.views import AgentConfigView, AgentView


class AgentService:
    def __init__(self, orchestrator: Orchestrator) -> None:
        self._orchestrator = orchestrator

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_agent(
        self,
        workspace_name: str,
        name: str,
        description: str,
        system_prompt: str,
        provider: str | None = None,
        model: str | None = None,
        allowed_tools: list[str] | None = None,
    ) -> AgentView:
        ws = self._get_workspace_or_raise(workspace_name)
        if ws.get_agent(name) is not None:
            raise AlreadyExistsError("agent", name)
        config = AgentConfig(
            name=name,
            description=description,
            system_prompt=system_prompt,
            provider=provider,
            model=model,
            allowed_tools=allowed_tools or [],
        )
        agent = self._orchestrator.create_agent(config, workspace_name)
        return self._to_view(agent)

    def list_agents(self, workspace_name: str) -> list[AgentView]:
        ws = self._get_workspace_or_raise(workspace_name)
        return [
            self._to_view(agent)
            for agent_name in ws.list_agents()
            if (agent := ws.get_agent(agent_name)) is not None
        ]

    def get_agent(self, workspace_name: str, agent_name: str) -> AgentView:
        ws = self._get_workspace_or_raise(workspace_name)
        agent = self._get_agent_or_raise(ws, agent_name)
        return self._to_view(agent)

    def update_agent(
        self,
        workspace_name: str,
        agent_name: str,
        *,
        description: str | None = None,
        system_prompt: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        allowed_tools: list[str] | None = None,
    ) -> AgentView:
        """Update an agent's config by rebuilding it.

        Note: rebuilding creates a new Agent instance, which resets conversation history.
        """
        ws = self._get_workspace_or_raise(workspace_name)
        existing = self._get_agent_or_raise(ws, agent_name)
        c = existing.config
        new_config = AgentConfig(
            name=c.name,
            description=description if description is not None else c.description,
            system_prompt=system_prompt if system_prompt is not None else c.system_prompt,
            provider=provider if provider is not None else c.provider,
            model=model if model is not None else c.model,
            allowed_tools=allowed_tools if allowed_tools is not None else list(c.allowed_tools),
        )
        agent = self._orchestrator.replace_agent(new_config, workspace_name)
        return self._to_view(agent)

    def delete_agent(self, workspace_name: str, agent_name: str) -> None:
        ws = self._get_workspace_or_raise(workspace_name)
        self._get_agent_or_raise(ws, agent_name)
        ws.remove_agent(agent_name)

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    async def run_agent(self, workspace_name: str, agent_name: str, message: str) -> str:
        """Send a message to an agent and return its full text response."""
        ws = self._get_workspace_or_raise(workspace_name)
        agent = self._get_agent_or_raise(ws, agent_name)
        return await agent.run(message)

    async def stream_agent(
        self, workspace_name: str, agent_name: str, message: str
    ) -> AsyncIterator[str]:
        """Stream an agent's response token by token as plain strings."""
        ws = self._get_workspace_or_raise(workspace_name)
        agent = self._get_agent_or_raise(ws, agent_name)
        async for msg in agent.stream(message):
            content = msg.content
            yield content if isinstance(content, str) else str(content)

    def reset_agent(self, workspace_name: str, agent_name: str) -> None:
        """Clear an agent's conversation history."""
        ws = self._get_workspace_or_raise(workspace_name)
        agent = self._get_agent_or_raise(ws, agent_name)
        agent.reset()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_workspace_or_raise(self, workspace_name: str) -> Workspace:
        ws = self._orchestrator.get_workspace(workspace_name)
        if ws is None:
            raise NotFoundError("workspace", workspace_name)
        return ws

    def _get_agent_or_raise(self, ws: Workspace, agent_name: str) -> Agent:
        agent = ws.get_agent(agent_name)
        if agent is None:
            raise NotFoundError("agent", agent_name)
        return agent

    def _to_view(self, agent: Agent) -> AgentView:
        return AgentView(
            config=AgentConfigView(
                name=agent.config.name,
                description=agent.config.description,
                system_prompt=agent.config.system_prompt,
                provider=agent.config.provider,
                model=agent.config.model,
                allowed_tools=list(agent.config.allowed_tools),
            ),
            tools=agent.tools,
            llm_info=agent.get_llm_info(),
        )
