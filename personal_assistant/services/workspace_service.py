from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.services.conversation_service import ConversationService
from personal_assistant.services.exceptions import (
    AlreadyExistsError,
    NotFoundError,
    ServiceValidationError,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
from personal_assistant.core.workspace import Workspace, WorkspaceConfig
from personal_assistant.services.views import (
    AgentConfigView,
    AgentView,
    WorkspaceChatView,
    WorkspaceDetailView,
    WorkspaceView,
)


class WorkspaceService:
    def __init__(
        self,
        orchestrator: Orchestrator,
        conversation_service: ConversationService | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._conversation_service = conversation_service

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
    # Chat (workspace-level routing)
    # ------------------------------------------------------------------

    async def chat(
        self,
        workspace_name: str,
        message: str,
        conversation_id: str | None = None,
        agent_name: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        session: AsyncSession | None = None,
    ) -> WorkspaceChatView:
        """Route a message to the workspace supervisor or a specific agent.

        Args:
            workspace_name: Target workspace.
            message: User message.
            conversation_id: Conversation ID string. Generated if not provided.
            agent_name: Skip the supervisor and target this agent directly.
            provider: Override provider for this turn (requires agent_name).
            model: Override model for this turn (requires agent_name).
            session: Optional DB session.

        Returns:
            ``WorkspaceChatView`` with the response, conversation_id, and agent used.

        Raises:
            NotFoundError: If the workspace or agent does not exist.
            ServiceValidationError: If provider/model is set without agent_name,
                                    or if conversation_id is not a valid UUID.
        """
        if (provider is not None or model is not None) and agent_name is None:
            raise ServiceValidationError("provider/model override requires agent_name to be set")

        self._get_or_raise(workspace_name)

        if agent_name is not None:
            if self._conversation_service is None:
                raise ServiceValidationError(
                    "ConversationService is required for agent-direct workspace chat"
                )

            conv_uuid: uuid.UUID | None = None
            if conversation_id is not None:
                try:
                    conv_uuid = uuid.UUID(conversation_id)
                except ValueError:
                    raise ServiceValidationError(
                        f"conversation_id is not a valid UUID: {conversation_id!r}"
                    ) from None

            llm_override = None
            if provider is not None or model is not None:
                registry = self._orchestrator.registry
                resolved_provider = registry.get(provider)
                llm_override = resolved_provider.get_model(model)

            clone, returned_uuid = await self._conversation_service.get_or_create_clone(
                workspace_name,
                agent_name,
                conv_uuid,
                session,
                llm_override=llm_override,
            )
            response = await clone.run(message, session)
            return WorkspaceChatView(
                response=response,
                conversation_id=str(returned_uuid),
                agent_used=agent_name,
            )

        # Supervisor path
        response, returned_thread_id, agent_used = await self._orchestrator.delegate_to_workspace(
            task=message,
            workspace_name=workspace_name,
            thread_id=conversation_id,
            session=session,
        )
        return WorkspaceChatView(
            response=response,
            conversation_id=returned_thread_id,
            agent_used=agent_used,
        )

    async def stream_chat(
        self,
        workspace_name: str,
        message: str,
        conversation_id: str | None = None,
        agent_name: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        session: AsyncSession | None = None,
    ) -> tuple[AsyncIterator[str], str, str]:
        """Stream a response from a specific agent in the workspace.

        Only the agent-direct path is supported. Supervisor streaming requires
        LangGraph graph-level changes and is a future enhancement.

        Args:
            workspace_name: Target workspace.
            message: User message.
            conversation_id: Conversation ID string. Generated if not provided.
            agent_name: Target agent (required).
            provider: Override provider for this turn.
            model: Override model for this turn.
            session: Optional DB session.

        Returns:
            Tuple of (token_iterator, conversation_id_str, agent_name).

        Raises:
            ServiceValidationError: If agent_name is not provided.
        """
        if agent_name is None:
            raise ServiceValidationError(
                "stream_chat requires agent_name; supervisor streaming is not supported"
            )
        if (provider is not None or model is not None) and agent_name is None:
            raise ServiceValidationError("provider/model override requires agent_name to be set")

        if self._conversation_service is None:
            raise ServiceValidationError(
                "ConversationService is required for streaming workspace chat"
            )

        self._get_or_raise(workspace_name)

        conv_uuid: uuid.UUID | None = None
        if conversation_id is not None:
            try:
                conv_uuid = uuid.UUID(conversation_id)
            except ValueError:
                raise ServiceValidationError(
                    f"conversation_id is not a valid UUID: {conversation_id!r}"
                ) from None

        llm_override = None
        if provider is not None or model is not None:
            registry = self._orchestrator.registry
            resolved_provider = registry.get(provider)
            llm_override = resolved_provider.get_model(model)

        clone, returned_uuid = await self._conversation_service.get_or_create_clone(
            workspace_name,
            agent_name,
            conv_uuid,
            session,
            llm_override=llm_override,
        )

        async def _token_iter() -> AsyncIterator[str]:
            from langchain_core.messages import AIMessage

            async for msg in clone.stream(message, session):
                if isinstance(msg, AIMessage):
                    content = msg.content
                    if isinstance(content, str):
                        yield content

        return _token_iter(), str(returned_uuid), agent_name

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
