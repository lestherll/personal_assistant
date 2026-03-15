"""DB-first, stateless AgentService.

Each method receives ``user_id`` and ``session`` as explicit arguments.
The service is a singleton — it holds no per-user or per-request state.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from personal_assistant.core.agent import Agent, AgentConfig, row_to_message
from personal_assistant.persistence.repository import ConversationRepository
from personal_assistant.persistence.user_workspace_repository import UserWorkspaceRepository
from personal_assistant.services.conversation_cache import ConversationCache
from personal_assistant.services.exceptions import AlreadyExistsError, NotFoundError
from personal_assistant.services.views import AgentConfigView, AgentView, ConversationView

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool
    from sqlalchemy.ext.asyncio import AsyncSession

    from personal_assistant.persistence.models import UserAgent, UserWorkspace
    from personal_assistant.providers.registry import ProviderRegistry


class AgentService:
    """Stateless agent CRUD + chat service backed by the DB.

    Args:
        registry: Provider registry for resolving LLMs.
        tools: All available tools; filtered per agent via ``allowed_tools``.
        cache: Conversation history cache.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        tools: list[BaseTool],
        cache: ConversationCache,
    ) -> None:
        self._registry = registry
        self._tools = tools
        self._cache = cache

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_agent(
        self,
        user_id: uuid.UUID,
        workspace_name: str,
        name: str,
        description: str,
        system_prompt: str,
        provider: str | None = None,
        model: str | None = None,
        allowed_tools: list[str] | None = None,
        session: AsyncSession | None = None,
    ) -> AgentView:
        if session is None:
            raise NotFoundError("workspace", workspace_name)

        repo = UserWorkspaceRepository(session)
        ws_row = await repo.get_workspace(user_id, workspace_name)
        if ws_row is None:
            raise NotFoundError("workspace", workspace_name)

        existing = await repo.get_agent(ws_row.id, name)
        if existing is not None:
            raise AlreadyExistsError("agent", name)

        agent_row = await repo.create_agent(
            ws_row.id, name, description, system_prompt, provider, model, allowed_tools or []
        )
        return self._row_to_view(agent_row)

    async def list_agents(
        self,
        user_id: uuid.UUID,
        workspace_name: str,
        session: AsyncSession | None = None,
    ) -> list[AgentView]:
        if session is None:
            raise NotFoundError("workspace", workspace_name)

        repo = UserWorkspaceRepository(session)
        ws_row = await repo.get_workspace(user_id, workspace_name)
        if ws_row is None:
            raise NotFoundError("workspace", workspace_name)

        rows = await repo.list_agents(ws_row.id)
        return [self._row_to_view(r) for r in rows]

    async def get_agent(
        self,
        user_id: uuid.UUID,
        workspace_name: str,
        agent_name: str,
        session: AsyncSession | None = None,
    ) -> AgentView:
        _ws_row, agent_row = await self._get_ws_and_agent_or_raise(
            user_id, workspace_name, agent_name, session
        )
        return self._row_to_view(agent_row)

    async def update_agent(
        self,
        user_id: uuid.UUID,
        workspace_name: str,
        agent_name: str,
        *,
        description: str | None = None,
        system_prompt: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        allowed_tools: list[str] | None = None,
        session: AsyncSession | None = None,
    ) -> AgentView:
        ws_row, agent_row = await self._get_ws_and_agent_or_raise(
            user_id, workspace_name, agent_name, session
        )
        assert session is not None  # guaranteed by _get_ws_and_agent_or_raise

        repo = UserWorkspaceRepository(session)
        updated = await repo.upsert_agent(
            ws_row.id,
            agent_row.name,
            description if description is not None else agent_row.description,
            system_prompt if system_prompt is not None else agent_row.system_prompt,
            provider if provider is not None else agent_row.provider,
            model if model is not None else agent_row.model,
            allowed_tools if allowed_tools is not None else list(agent_row.allowed_tools),
        )
        return self._row_to_view(updated)

    async def delete_agent(
        self,
        user_id: uuid.UUID,
        workspace_name: str,
        agent_name: str,
        session: AsyncSession | None = None,
    ) -> None:
        ws_row, _agent_row = await self._get_ws_and_agent_or_raise(
            user_id, workspace_name, agent_name, session
        )
        assert session is not None  # guaranteed by _get_ws_and_agent_or_raise

        repo = UserWorkspaceRepository(session)
        await repo.delete_agent(ws_row.id, agent_name)

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    async def run_agent(
        self,
        user_id: uuid.UUID | None,
        workspace_name: str,
        agent_name: str,
        message: str,
        *,
        conversation_id: uuid.UUID | None,
        session: AsyncSession | None,
    ) -> tuple[str, uuid.UUID]:
        """Send a message to an agent and return ``(reply, conversation_id)``."""
        agent, _ = await self._prepare_agent(
            user_id, workspace_name, agent_name, conversation_id, session
        )
        reply = await agent.run(message, session=session)
        # Update cache with post-run history
        await self._cache.set(user_id, workspace_name, agent.conversation_id, agent.history)  # type: ignore[arg-type]
        return reply, agent.conversation_id  # type: ignore[return-value]

    async def stream_agent(
        self,
        user_id: uuid.UUID | None,
        workspace_name: str,
        agent_name: str,
        message: str,
        *,
        conversation_id: uuid.UUID | None,
        session: AsyncSession | None,
    ) -> tuple[AsyncIterator[str], uuid.UUID]:
        """Resolve the conversation then return ``(token_iterator, conversation_id)``.

        The conversation_id is resolved before any tokens are yielded so callers
        can surface errors as proper HTTP responses rather than SSE events.
        """
        agent, _ = await self._prepare_agent(
            user_id, workspace_name, agent_name, conversation_id, session
        )
        resolved_conv_id: uuid.UUID = agent.conversation_id  # type: ignore[assignment]

        async def _generate() -> AsyncIterator[str]:
            async for msg in agent.stream(message, session=session):
                content = msg.content
                yield content if isinstance(content, str) else str(content)
            # Update cache after stream completes
            await self._cache.set(user_id, workspace_name, resolved_conv_id, agent.history)  # type: ignore[arg-type]

        return _generate(), resolved_conv_id

    async def list_conversations(
        self,
        user_id: uuid.UUID | None,
        workspace_name: str,
        session: AsyncSession,
    ) -> list[ConversationView]:
        """List all conversations for a workspace (requires DB session)."""
        if user_id is None:
            raise NotFoundError("workspace", workspace_name)

        repo = ConversationRepository(session)
        convs = await repo.list_conversations(workspace_name, user_id=user_id)
        return [
            ConversationView(
                id=c.id,
                workspace_name=c.workspace_name,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in convs
        ]

    async def delete_conversation(
        self,
        user_id: uuid.UUID | None,
        workspace_name: str,
        conversation_id: uuid.UUID,
        session: AsyncSession,
    ) -> None:
        """Delete a conversation and invalidate its cache entry."""
        conv_repo = ConversationRepository(session)
        conv = await conv_repo.get_conversation_for_workspace(
            conversation_id, workspace_name, user_id=user_id
        )
        if conv is None:
            raise NotFoundError("conversation", str(conversation_id))

        await session.delete(conv)
        await session.commit()

        if user_id is not None:
            await self._cache.invalidate(user_id, workspace_name, conversation_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_ws_and_agent_or_raise(
        self,
        user_id: uuid.UUID | None,
        workspace_name: str,
        agent_name: str,
        session: AsyncSession | None,
    ) -> tuple[UserWorkspace, UserAgent]:
        if session is None or user_id is None:
            raise NotFoundError("workspace", workspace_name)

        repo = UserWorkspaceRepository(session)
        ws_row = await repo.get_workspace(user_id, workspace_name)
        if ws_row is None:
            raise NotFoundError("workspace", workspace_name)

        agent_row = await repo.get_agent(ws_row.id, agent_name)
        if agent_row is None:
            raise NotFoundError("agent", agent_name)

        return ws_row, agent_row

    async def _prepare_agent(
        self,
        user_id: uuid.UUID | None,
        workspace_name: str,
        agent_name: str,
        conversation_id: uuid.UUID | None,
        session: AsyncSession | None,
    ) -> tuple[Agent, uuid.UUID | None]:
        """Load config from DB, build an ephemeral Agent, bind conversation state."""
        if session is None or user_id is None:
            raise NotFoundError("workspace", workspace_name)

        ws_repo = UserWorkspaceRepository(session)
        ws_row = await ws_repo.get_workspace(user_id, workspace_name)
        if ws_row is None:
            raise NotFoundError("workspace", workspace_name)

        agent_row = await ws_repo.get_agent(ws_row.id, agent_name)
        if agent_row is None:
            raise NotFoundError("agent", agent_name)

        config = AgentConfig(
            name=agent_row.name,
            description=agent_row.description,
            system_prompt=agent_row.system_prompt,
            provider=agent_row.provider,
            model=agent_row.model,
            allowed_tools=list(agent_row.allowed_tools),
        )
        agent = Agent(config, self._registry, tools=self._tools)

        conv_repo = ConversationRepository(session)

        if conversation_id is not None:
            conv = await conv_repo.get_conversation_for_workspace(
                conversation_id, workspace_name, user_id=user_id
            )
            if conv is None:
                raise NotFoundError("conversation", str(conversation_id))

            cached = await self._cache.get(user_id, workspace_name, conversation_id)
            if cached is not None:
                history = cached
            else:
                rows = await conv_repo.load_messages(conversation_id)
                history = [row_to_message(r) for r in rows]
                await self._cache.set(user_id, workspace_name, conversation_id, history)

            agent.restore(history, conversation_id)
        else:
            await agent.start_conversation(session, workspace_name, user_id=user_id)

        return agent, agent.conversation_id

    def _row_to_view(self, row: UserAgent) -> AgentView:
        return AgentView(
            config=AgentConfigView(
                name=row.name,
                description=row.description,
                system_prompt=row.system_prompt,
                provider=row.provider,
                model=row.model,
                allowed_tools=list(row.allowed_tools),
            ),
            tools=list(row.allowed_tools),
            llm_info={"provider": row.provider, "model": row.model, "source": "registry"},
        )
