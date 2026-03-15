"""DB-first, stateless WorkspaceService.

Each method receives ``user_id`` and ``session`` as explicit arguments.
The service is a singleton — it holds no per-user or per-request state.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from personal_assistant.core.supervisor import AgentInfo, route
from personal_assistant.persistence.user_workspace_repository import UserWorkspaceRepository
from personal_assistant.services.exceptions import (
    AlreadyExistsError,
    NotFoundError,
    ServiceValidationError,
)
from personal_assistant.services.views import (
    AgentConfigView,
    AgentView,
    WorkspaceChatView,
    WorkspaceDetailView,
    WorkspaceView,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from personal_assistant.persistence.models import UserAgent, UserWorkspace
    from personal_assistant.providers.registry import ProviderRegistry
    from personal_assistant.services.agent_service import AgentService


class WorkspaceService:
    """Stateless workspace CRUD + chat service backed by the DB.

    Args:
        registry: Provider registry (used to resolve the routing LLM).
        agent_service: AgentService singleton for running agents.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        agent_service: AgentService,
    ) -> None:
        self._registry = registry
        self._agent_service = agent_service

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_workspace(
        self,
        user_id: uuid.UUID,
        name: str,
        description: str,
        metadata: dict[str, Any] | None = None,
        session: AsyncSession | None = None,
    ) -> WorkspaceView:
        if session is None:
            raise NotFoundError("workspace", name)

        repo = UserWorkspaceRepository(session)
        existing = await repo.get_workspace(user_id, name)
        if existing is not None:
            raise AlreadyExistsError("workspace", name)

        ws_row = await repo.create_workspace(user_id, name, description)
        return self._row_to_view(ws_row)

    async def list_workspaces(
        self,
        user_id: uuid.UUID,
        session: AsyncSession | None = None,
    ) -> list[WorkspaceView]:
        if session is None:
            return []

        repo = UserWorkspaceRepository(session)
        rows = await repo.list_workspaces(user_id)
        return [self._row_to_view(r) for r in rows]

    async def get_workspace(
        self,
        user_id: uuid.UUID,
        name: str,
        session: AsyncSession | None = None,
    ) -> WorkspaceDetailView:
        ws_row, agent_rows = await self._get_ws_or_raise(user_id, name, session)
        return self._row_to_detail_view(ws_row, agent_rows)

    async def update_workspace(
        self,
        user_id: uuid.UUID,
        name: str,
        *,
        description: str | None = None,
        session: AsyncSession | None = None,
    ) -> WorkspaceView:
        ws_row, _agent_rows = await self._get_ws_or_raise(user_id, name, session)
        assert session is not None  # guaranteed by _get_ws_or_raise

        repo = UserWorkspaceRepository(session)
        updated = await repo.upsert_workspace(
            user_id, name, description if description is not None else ws_row.description
        )
        return self._row_to_view(updated)

    async def delete_workspace(
        self,
        user_id: uuid.UUID,
        name: str,
        session: AsyncSession | None = None,
    ) -> None:
        await self._get_ws_or_raise(user_id, name, session)
        assert session is not None  # guaranteed by _get_ws_or_raise

        repo = UserWorkspaceRepository(session)
        await repo.delete_workspace(user_id, name)

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    async def chat(
        self,
        user_id: uuid.UUID | None,
        workspace_name: str,
        message: str,
        conversation_id: str | None = None,
        agent_name: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        session: AsyncSession | None = None,
    ) -> WorkspaceChatView:
        """Route a message to the supervisor or a specific agent."""
        if (provider is not None or model is not None) and agent_name is None:
            raise ServiceValidationError("provider/model override requires agent_name to be set")

        conv_uuid = self._parse_conversation_id(conversation_id)

        if agent_name is not None:
            reply, returned_id = await self._agent_service.run_agent(
                user_id,
                workspace_name,
                agent_name,
                message,
                conversation_id=conv_uuid,
                session=session,
            )
            return WorkspaceChatView(
                response=reply,
                conversation_id=str(returned_id),
                agent_used=agent_name,
            )

        # Supervisor path: load workspace agents, route, then run
        _ws_row, agent_rows = await self._get_ws_or_raise(user_id, workspace_name, session)
        if not agent_rows:
            raise ServiceValidationError(f"Workspace '{workspace_name}' has no agents to route to")

        routed_agent = await self._route(message, agent_rows)
        reply, returned_id = await self._agent_service.run_agent(
            user_id,
            workspace_name,
            routed_agent,
            message,
            conversation_id=conv_uuid,
            session=session,
        )
        return WorkspaceChatView(
            response=reply,
            conversation_id=str(returned_id),
            agent_used=routed_agent,
        )

    async def stream_chat(
        self,
        user_id: uuid.UUID | None,
        workspace_name: str,
        message: str,
        conversation_id: str | None = None,
        agent_name: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        session: AsyncSession | None = None,
    ) -> tuple[AsyncIterator[str], str, str]:
        """Stream a response. Requires ``agent_name``; supervisor streaming is not supported."""
        if agent_name is None:
            raise ServiceValidationError(
                "stream_chat requires agent_name; supervisor streaming is not supported"
            )

        conv_uuid = self._parse_conversation_id(conversation_id)

        token_iter, returned_id = await self._agent_service.stream_agent(
            user_id,
            workspace_name,
            agent_name,
            message,
            conversation_id=conv_uuid,
            session=session,
        )
        return token_iter, str(returned_id), agent_name

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_ws_or_raise(
        self,
        user_id: uuid.UUID | None,
        workspace_name: str,
        session: AsyncSession | None,
    ) -> tuple[UserWorkspace, list[UserAgent]]:
        if session is None or user_id is None:
            raise NotFoundError("workspace", workspace_name)

        repo = UserWorkspaceRepository(session)
        ws_row = await repo.get_workspace(user_id, workspace_name)
        if ws_row is None:
            raise NotFoundError("workspace", workspace_name)

        agent_rows = await repo.list_agents(ws_row.id)
        return ws_row, agent_rows

    async def _route(self, message: str, agent_rows: list[UserAgent]) -> str:
        """Use a lightweight LLM call to pick the best agent for this message."""
        agents = [AgentInfo(name=r.name, description=r.description) for r in agent_rows]
        llm = self._registry.get().get_model()
        return await route(message, agents, llm)

    @staticmethod
    def _parse_conversation_id(conversation_id: str | None) -> uuid.UUID | None:
        if conversation_id is None:
            return None
        try:
            return uuid.UUID(conversation_id)
        except ValueError:
            raise ServiceValidationError(
                f"conversation_id is not a valid UUID: {conversation_id!r}"
            ) from None

    def _row_to_view(self, row: UserWorkspace) -> WorkspaceView:
        return WorkspaceView(
            name=row.name,
            description=row.description,
            metadata={},
            agents=[],
            tools=[],
        )

    def _row_to_detail_view(
        self, row: UserWorkspace, agent_rows: list[UserAgent]
    ) -> WorkspaceDetailView:
        agents = [
            AgentView(
                config=AgentConfigView(
                    name=r.name,
                    description=r.description,
                    system_prompt=r.system_prompt,
                    provider=r.provider,
                    model=r.model,
                    allowed_tools=list(r.allowed_tools),
                ),
                tools=list(r.allowed_tools),
                llm_info={"provider": r.provider, "model": r.model, "source": "registry"},
            )
            for r in agent_rows
        ]
        return WorkspaceDetailView(
            name=row.name,
            description=row.description,
            metadata={},
            agents=agents,
            tools=[],
        )
