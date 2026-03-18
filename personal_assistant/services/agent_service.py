"""DB-first, stateless AgentService.

Each method receives ``user_id`` and ``session`` as explicit arguments.
The service is a singleton — it holds no per-user or per-request state.
"""

from __future__ import annotations

import asyncio
import collections
import logging
import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from langchain.chat_models import BaseChatModel
from langchain.messages import HumanMessage

from personal_assistant.core.agent import Agent, AgentConfig, row_to_message
from personal_assistant.persistence.repository import AgentParticipationView, ConversationRepository
from personal_assistant.persistence.user_workspace_repository import UserWorkspaceRepository
from personal_assistant.services.conversation_cache import ConversationCache
from personal_assistant.services.exceptions import AlreadyExistsError, NotFoundError
from personal_assistant.services.views import (
    AgentConfigView,
    AgentView,
    ConversationView,
    MessageView,
)

logger = logging.getLogger(__name__)

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
        self._locks: collections.OrderedDict[uuid.UUID, asyncio.Lock] = collections.OrderedDict()
        self._max_locks = 1000

    def _get_lock(self, conv_id: uuid.UUID) -> asyncio.Lock:
        """Return (or create) a per-conversation lock, evicting the oldest if over capacity."""
        if conv_id in self._locks:
            self._locks.move_to_end(conv_id)
            return self._locks[conv_id]
        lock = asyncio.Lock()
        self._locks[conv_id] = lock
        while len(self._locks) > self._max_locks:
            self._locks.popitem(last=False)
        return lock

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
            ws_row.id, name, description, system_prompt, provider, model, allowed_tools
        )
        return self._row_to_view(agent_row)

    async def list_agents(
        self,
        user_id: uuid.UUID,
        workspace_name: str,
        *,
        skip: int = 0,
        limit: int = 50,
        session: AsyncSession | None = None,
    ) -> list[AgentView]:
        if session is None:
            raise NotFoundError("workspace", workspace_name)

        repo = UserWorkspaceRepository(session)
        ws_row = await repo.get_workspace(user_id, workspace_name)
        if ws_row is None:
            raise NotFoundError("workspace", workspace_name)

        rows = await repo.list_agents(ws_row.id, skip=skip, limit=limit)
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
        assert session is not None  # nosec B101 — guaranteed by _get_ws_and_agent_or_raise

        repo = UserWorkspaceRepository(session)
        updated = await repo.upsert_agent(
            ws_row.id,
            agent_row.name,
            description if description is not None else agent_row.description,
            system_prompt if system_prompt is not None else agent_row.system_prompt,
            provider if provider is not None else agent_row.provider,
            model if model is not None else agent_row.model,
            allowed_tools if allowed_tools is not None else agent_row.allowed_tools,
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
        assert session is not None  # nosec B101 — guaranteed by _get_ws_and_agent_or_raise

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
        lock = self._get_lock(conversation_id) if conversation_id else None
        if lock:
            await lock.acquire()
        try:
            agent, ws_row = await self._prepare_agent(
                user_id, workspace_name, agent_name, conversation_id, session
            )
            is_first_turn = len(agent.history) == 0
            result = await agent.run(message, session=session)
            if is_first_turn and session is not None:
                assert user_id is not None  # nosec B101 — guaranteed by _prepare_agent
                assert agent.conversation_id is not None  # nosec B101 — created by start_conversation
                title = await _generate_title(message, agent.llm)
                await self.rename_conversation(
                    user_id=user_id,
                    workspace_name=workspace_name,
                    conversation_id=agent.conversation_id,
                    title=title,
                    session=session,
                )

            # Update cache with post-run history
            await self._cache.set(
                user_id,  # type: ignore[arg-type]
                ws_row.id,
                agent.conversation_id,  # type: ignore[arg-type]
                agent.history,
            )
            return result.content, agent.conversation_id  # type: ignore[return-value]
        finally:
            if lock:
                lock.release()

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
        lock = self._get_lock(conversation_id) if conversation_id else None
        if lock:
            await lock.acquire()

        try:
            agent, ws_row = await self._prepare_agent(
                user_id, workspace_name, agent_name, conversation_id, session
            )
        except BaseException:
            if lock:
                lock.release()
            raise

        resolved_conv_id: uuid.UUID = agent.conversation_id  # type: ignore[assignment]
        resolved_ws_id: uuid.UUID = ws_row.id

        is_first_turn = len(agent.history) == 0
        if is_first_turn and session is not None:
            assert user_id is not None  # nosec B101 — guaranteed by _prepare_agent
            title = await _generate_title(message, agent.llm)
            await self.rename_conversation(
                user_id=user_id,
                workspace_name=workspace_name,
                conversation_id=resolved_conv_id,
                title=title,
                session=session,
            )

        async def _generate() -> AsyncIterator[str]:
            try:
                async for msg_chunk in agent.stream(message, session=session):
                    content = msg_chunk.content
                    if isinstance(content, str) and content:
                        yield content
            except Exception:
                logger.exception("Stream error for conversation %s", resolved_conv_id)
                # Best-effort: save partial history so the turn isn't lost
                try:
                    await self._cache.set(
                        user_id,  # type: ignore[arg-type]
                        resolved_ws_id,
                        resolved_conv_id,
                        agent.history,
                    )
                except Exception:
                    logger.warning("Failed to save partial history after stream error")
                raise
            else:
                # Update cache after stream completes successfully
                await self._cache.set(
                    user_id,  # type: ignore[arg-type]
                    resolved_ws_id,
                    resolved_conv_id,
                    agent.history,
                )
            finally:
                if lock:
                    lock.release()

        return _generate(), resolved_conv_id

    async def list_conversations(
        self,
        user_id: uuid.UUID | None,
        workspace_name: str,
        session: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ConversationView]:
        """List all conversations for a workspace (requires DB session)."""
        if user_id is None:
            raise NotFoundError("workspace", workspace_name)

        ws_repo = UserWorkspaceRepository(session)
        ws_row = await ws_repo.get_workspace(user_id, workspace_name)
        if ws_row is None:
            raise NotFoundError("workspace", workspace_name)

        conv_repo = ConversationRepository(session)
        convs = await conv_repo.list_conversations(
            ws_row.id,
            user_id=user_id,
            skip=skip,
            limit=limit,
        )
        return [
            ConversationView(
                id=c.id,
                workspace_id=c.workspace_id,
                user_id=c.user_id,
                created_at=c.created_at,
                updated_at=c.updated_at,
                title=c.title,
            )
            for c in convs
        ]

    async def list_agent_participation(
        self,
        user_id: uuid.UUID | None,
        workspace_name: str,
        conversation_id: uuid.UUID,
        session: AsyncSession,
    ) -> list[AgentParticipationView]:
        """Return agent participation breakdown for a conversation."""
        if user_id is None:
            raise NotFoundError("workspace", workspace_name)

        ws_repo = UserWorkspaceRepository(session)
        ws_row = await ws_repo.get_workspace(user_id, workspace_name)
        if ws_row is None:
            raise NotFoundError("workspace", workspace_name)

        conv_repo = ConversationRepository(session)
        conv = await conv_repo.get_conversation_for_workspace(
            conversation_id, ws_row.id, user_id=user_id
        )
        if conv is None:
            raise NotFoundError("conversation", str(conversation_id))

        return await conv_repo.list_agent_participation(conversation_id)

    async def get_conversation_messages(
        self,
        user_id: uuid.UUID | None,
        workspace_name: str,
        conversation_id: uuid.UUID,
        session: AsyncSession,
    ) -> list[MessageView]:
        """Return all messages in a conversation, ordered by sequence."""
        if user_id is None:
            raise NotFoundError("workspace", workspace_name)

        ws_repo = UserWorkspaceRepository(session)
        ws_row = await ws_repo.get_workspace(user_id, workspace_name)
        if ws_row is None:
            raise NotFoundError("workspace", workspace_name)

        conv_repo = ConversationRepository(session)
        conv = await conv_repo.get_conversation_for_workspace(
            conversation_id, ws_row.id, user_id=user_id
        )
        if conv is None:
            raise NotFoundError("conversation", str(conversation_id))

        messages = await conv_repo.load_messages(conversation_id)
        return [
            MessageView(
                id=m.id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                agent_id=m.agent_id,
                created_at=m.created_at,
            )
            for m in messages
        ]

    async def delete_conversation(
        self,
        user_id: uuid.UUID | None,
        workspace_name: str,
        conversation_id: uuid.UUID,
        session: AsyncSession,
    ) -> None:
        """Delete a conversation and invalidate its cache entry."""
        if user_id is None:
            raise NotFoundError("conversation", str(conversation_id))

        ws_repo = UserWorkspaceRepository(session)
        ws_row = await ws_repo.get_workspace(user_id, workspace_name)
        if ws_row is None:
            raise NotFoundError("workspace", workspace_name)

        conv_repo = ConversationRepository(session)
        conv = await conv_repo.get_conversation_for_workspace(
            conversation_id, ws_row.id, user_id=user_id
        )
        if conv is None:
            raise NotFoundError("conversation", str(conversation_id))

        await session.delete(conv)
        await session.commit()

        await self._cache.invalidate(user_id, ws_row.id, conversation_id)

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
    ) -> tuple[Agent, UserWorkspace]:
        """Load config from DB, build an ephemeral Agent, bind conversation state.

        Returns ``(agent, ws_row)`` so callers can access ``ws_row.id`` for
        cache key construction without a second DB round-trip.
        """
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
            allowed_tools=list(agent_row.allowed_tools)
            if agent_row.allowed_tools is not None
            else None,
            agent_id=agent_row.id,
        )
        agent = Agent(config, self._registry, tools=self._tools)

        conv_repo = ConversationRepository(session)

        if conversation_id is not None:
            conv = await conv_repo.get_conversation_for_workspace(
                conversation_id, ws_row.id, user_id=user_id
            )
            if conv is None:
                raise NotFoundError("conversation", str(conversation_id))

            cached = await self._cache.get(user_id, ws_row.id, conversation_id)
            if cached is not None:
                history = cached
            else:
                rows = await conv_repo.load_messages(conversation_id)
                history = [row_to_message(r) for r in rows]
                await self._cache.set(user_id, ws_row.id, conversation_id, history)

            agent.restore(history, conversation_id)
        else:
            await agent.start_conversation(session, ws_row.id, user_id=user_id)

        return agent, ws_row

    def _row_to_view(self, row: UserAgent) -> AgentView:
        if row.allowed_tools is not None:
            allowed = set(row.allowed_tools)
            resolved_tools = [t.name for t in self._tools if t.name in allowed]
        else:
            resolved_tools = [t.name for t in self._tools]
        return AgentView(
            config=AgentConfigView(
                name=row.name,
                description=row.description,
                system_prompt=row.system_prompt,
                provider=row.provider,
                model=row.model,
                allowed_tools=list(row.allowed_tools) if row.allowed_tools is not None else None,
            ),
            tools=resolved_tools,
            llm_info={"provider": row.provider, "model": row.model, "source": "registry"},
        )

    async def rename_conversation(
        self,
        user_id: uuid.UUID,
        workspace_name: str,
        conversation_id: uuid.UUID,
        title: str,
        session: AsyncSession,
    ) -> None:
        """Rename a conversation. Raises NotFoundError if not found or not owned by user."""
        ws_repo = UserWorkspaceRepository(session)
        ws_row = await ws_repo.get_workspace(user_id, workspace_name)
        if ws_row is None:
            raise NotFoundError("workspace", workspace_name)

        repo = ConversationRepository(session)
        conv = await repo.get_conversation_for_workspace(
            conversation_id,
            ws_row.id,
            user_id=user_id,
        )
        if conv is None:
            raise NotFoundError("conversation", str(conversation_id))

        await repo.update_title(conversation_id, title)
        await session.commit()


async def _generate_title(message: str, llm: BaseChatModel) -> str:
    prompt = (
        "Generate a concise 4-6 word title for a conversation that begins with "
        f"this message. Reply with just the title, no punctuation:\n\n{message}"
    )
    result = await llm.ainvoke([HumanMessage(content=prompt)])
    return str(result.content).strip()[:255]
