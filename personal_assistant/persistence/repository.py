from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from personal_assistant.persistence.models import Conversation, Message


class ConversationRepository:
    """Data-access layer for Conversation and Message records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    async def create_conversation(
        self, agent_name: str, workspace_name: str | None = None
    ) -> Conversation:
        """Insert a new conversation row and return it."""
        conv = Conversation(agent_name=agent_name, workspace_name=workspace_name)
        self._session.add(conv)
        await self._session.commit()
        await self._session.refresh(conv)
        return conv

    async def get_conversation(self, conversation_id: uuid.UUID) -> Conversation | None:
        result = await self._session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def touch_conversation(self, conversation_id: uuid.UUID) -> None:
        """Bump the updated_at timestamp of a conversation."""
        conv = await self.get_conversation(conversation_id)
        if conv:
            conv.updated_at = datetime.now(timezone.utc)
            await self._session.commit()

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    async def load_messages(self, conversation_id: uuid.UUID) -> list[Message]:
        """Return all messages in a conversation, ordered by creation time."""
        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        return list(result.scalars().all())

    async def save_message(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> Message:
        """Insert a new message row and return it."""
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            extra_metadata=metadata,
        )
        self._session.add(msg)
        await self._session.commit()
        return msg
