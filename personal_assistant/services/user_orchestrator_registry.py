from __future__ import annotations

import uuid

from personal_assistant.core.agent import Agent, AgentConfig
from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.core.workspace import Workspace, WorkspaceConfig
from personal_assistant.persistence.models import UserAgent, UserWorkspace


class UserOrchestratorRegistry:
    """In-memory cache mapping user IDs to their personal Orchestrator instances.

    The template Orchestrator is used only to share the ProviderRegistry;
    it is never mutated by user operations.
    """

    def __init__(self, template: Orchestrator) -> None:
        self._template = template
        self._store: dict[uuid.UUID, Orchestrator] = {}

    def get(self, user_id: uuid.UUID) -> Orchestrator | None:
        """Return the cached orchestrator for a user, or None on miss."""
        return self._store.get(user_id)

    def build_and_cache(
        self,
        user_id: uuid.UUID,
        user_ws_rows: list[UserWorkspace],
        user_agent_rows: dict[uuid.UUID, list[UserAgent]],
    ) -> Orchestrator:
        """Build a fresh Orchestrator from DB rows and cache it."""
        orch = Orchestrator(self._template.registry)
        for ws_row in user_ws_rows:
            ws = Workspace(WorkspaceConfig(name=ws_row.name, description=ws_row.description))
            for agent_row in user_agent_rows.get(ws_row.id, []):
                agent_config = AgentConfig(
                    name=agent_row.name,
                    description=agent_row.description,
                    system_prompt=agent_row.system_prompt,
                    provider=agent_row.provider,
                    model=agent_row.model,
                    allowed_tools=list(agent_row.allowed_tools or []),
                )
                agent = Agent(agent_config, self._template.registry)
                ws.add_agent(agent)
            orch.add_workspace(ws)
        self._store[user_id] = orch
        return orch

    def invalidate(self, user_id: uuid.UUID) -> None:
        """Evict a user's orchestrator from the cache."""
        self._store.pop(user_id, None)
