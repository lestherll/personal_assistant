from __future__ import annotations

from typing import Any

from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.core.workspace import Workspace, WorkspaceConfig
from personal_assistant.services.exceptions import AlreadyExistsError, NotFoundError
from personal_assistant.services.views import (
    AgentConfigView,
    AgentView,
    WorkspaceDetailView,
    WorkspaceView,
)


class WorkspaceService:
    def __init__(self, orchestrator: Orchestrator) -> None:
        self._orchestrator = orchestrator

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_workspace(
        self,
        name: str,
        description: str,
        metadata: dict[str, Any] | None = None,
    ) -> WorkspaceView:
        if self._orchestrator.get_workspace(name) is not None:
            raise AlreadyExistsError("workspace", name)
        config = WorkspaceConfig(name=name, description=description, metadata=metadata or {})
        ws = self._orchestrator.create_workspace(config)
        return self._to_view(ws)

    def list_workspaces(self) -> list[WorkspaceView]:
        return [
            self._to_view(ws)
            for name in self._orchestrator.list_workspaces()
            if (ws := self._orchestrator.get_workspace(name)) is not None
        ]

    def get_workspace(self, name: str) -> WorkspaceDetailView:
        ws = self._get_or_raise(name)
        return self._to_detail_view(ws)

    def update_workspace(
        self,
        name: str,
        *,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WorkspaceView:
        ws = self._get_or_raise(name)
        if description is not None:
            ws.config.description = description
        if metadata is not None:
            ws.config.metadata = metadata
        return self._to_view(ws)

    def delete_workspace(self, name: str) -> None:
        self._get_or_raise(name)
        self._orchestrator.remove_workspace(name)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_or_raise(self, name: str) -> Workspace:
        ws = self._orchestrator.get_workspace(name)
        if ws is None:
            raise NotFoundError("workspace", name)
        return ws

    def _to_view(self, ws: Workspace) -> WorkspaceView:
        return WorkspaceView(
            name=ws.config.name,
            description=ws.config.description,
            metadata=ws.config.metadata,
            agents=ws.list_agents(),
            tools=ws.list_tools(),
        )

    def _to_detail_view(self, ws: Workspace) -> WorkspaceDetailView:
        agents = [
            AgentView(
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
            for agent_name in ws.list_agents()
            if (agent := ws.get_agent(agent_name)) is not None
        ]
        return WorkspaceDetailView(
            name=ws.config.name,
            description=ws.config.description,
            metadata=ws.config.metadata,
            agents=agents,
            tools=ws.list_tools(),
        )
