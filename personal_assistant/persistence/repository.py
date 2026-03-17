from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from personal_assistant.persistence.models import Conversation, Message, MessageRole, UserAgent


@dataclass
class AgentParticipationView:
    """How many messages a given agent contributed to a conversation."""

    agent_id: uuid.UUID
    agent_name: str
    message_count: int


class ConversationRepository:
    """Data-access layer for Conversation and Message records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    async def create_conversation(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        title: str | None = None,
    ) -> Conversation:
        """Insert a new conversation row and return it."""
        conv = Conversation(workspace_id=workspace_id, user_id=user_id, title=title)
        self._session.add(conv)
        await self._session.commit()
        await self._session.refresh(conv)
        return conv

    async def get_conversation(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> Conversation | None:
        conditions = [Conversation.id == conversation_id]
        if user_id is not None:
            conditions.append(Conversation.user_id == user_id)
        result = await self._session.execute(select(Conversation).where(*conditions))
        return result.scalar_one_or_none()

    async def touch_conversation(self, conversation_id: uuid.UUID) -> None:
        """Bump the updated_at timestamp of a conversation."""
        conv = await self.get_conversation(conversation_id)
        if conv:
            conv.updated_at = datetime.now(UTC)
            await self._session.commit()

    async def update_title(self, conversation_id: uuid.UUID, title: str) -> None:
        await self._session.execute(
            update(Conversation).where(Conversation.id == conversation_id).values(title=title)
        )
        await self._session.flush()

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    async def load_messages(self, conversation_id: uuid.UUID) -> list[Message]:
        """Return all messages in a conversation, ordered by sequence_index then created_at."""
        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.sequence_index, Message.created_at)
        )
        return list(result.scalars().all())

    async def get_conversation_for_workspace(
        self,
        conversation_id: uuid.UUID,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> Conversation | None:
        """Return the conversation only if it belongs to the given workspace (and user)."""
        conditions = [
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace_id,
        ]
        if user_id is not None:
            conditions.append(Conversation.user_id == user_id)
        result = await self._session.execute(select(Conversation).where(*conditions))
        return result.scalar_one_or_none()

    async def list_conversations(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> list[Conversation]:
        """Return all conversations for a workspace, ordered by creation time."""
        conditions = [Conversation.workspace_id == workspace_id]
        if user_id is not None:
            conditions.append(Conversation.user_id == user_id)
        result = await self._session.execute(
            select(Conversation).where(*conditions).order_by(Conversation.created_at)
        )
        return list(result.scalars().all())

    async def delete_conversation(self, conversation_id: uuid.UUID) -> bool:
        """Delete a conversation and its messages. Returns True if deleted, False if not found."""
        conv = await self.get_conversation(conversation_id)
        if conv is None:
            return False
        await self._session.delete(conv)
        await self._session.commit()
        return True

    async def add_message(
        self,
        conversation_id: uuid.UUID,
        role: MessageRole,
        content: str,
        *,
        agent_id: uuid.UUID | None = None,
        provider: str | None = None,
        model: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        extra_metadata: dict[str, object] | None = None,
    ) -> Message:
        """Insert a new message row and return it.

        ``sequence_index`` is assigned by taking a row-level lock on the parent
        conversation to prevent duplicates under concurrent writes.
        """
        # Lock the conversation row to serialise sequence_index assignment
        await self._session.execute(
            select(Conversation).where(Conversation.id == conversation_id).with_for_update()
        )
        max_seq = await self._session.scalar(
            select(func.max(Message.sequence_index)).where(
                Message.conversation_id == conversation_id
            )
        )
        next_seq = (max_seq or 0) + 1

        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            agent_id=agent_id,
            sequence_index=next_seq,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            extra_metadata=extra_metadata,
        )
        self._session.add(msg)
        await self._session.commit()
        return msg

    async def list_agent_participation(
        self, conversation_id: uuid.UUID
    ) -> list[AgentParticipationView]:
        """Return which agents contributed messages to a conversation, with message counts."""
        rows = await self._session.execute(
            select(
                Message.agent_id,
                UserAgent.name,
                func.count(Message.id).label("message_count"),
            )
            .join(UserAgent, Message.agent_id == UserAgent.id)
            .where(
                Message.conversation_id == conversation_id,
                Message.agent_id.is_not(None),
            )
            .group_by(Message.agent_id, UserAgent.name)
        )
        return [
            AgentParticipationView(
                agent_id=row.agent_id,
                agent_name=row.name,
                message_count=row.message_count,
            )
            for row in rows
        ]
