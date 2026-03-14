from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from personal_assistant.core.agent import Agent
from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.services.conversation_pool import ConversationPool
from personal_assistant.services.exceptions import NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ConversationService:
    def __init__(self, orchestrator: Orchestrator, pool: ConversationPool) -> None:
        self._orchestrator = orchestrator
        self._pool = pool

    async def get_or_create_clone(
        self,
        workspace_name: str,
        agent_name: str,
        conversation_id: uuid.UUID | None,
        session: AsyncSession | None,
    ) -> tuple[Agent, uuid.UUID]:
        """Return (clone, conversation_id) for a request.

        - Pool hit: return existing clone.
        - New conversation (id=None): clone template, start_conversation (or generate UUID).
        - Cold-start with id: validate against DB, clone template, bind id for lazy reload.
        """
        if conversation_id is not None:
            clone = self._pool.get(workspace_name, agent_name, conversation_id)
            if clone is not None:
                return clone, conversation_id

            # Cold-start: need DB to validate
            if session is None:
                raise NotFoundError("conversation", str(conversation_id))

            from personal_assistant.persistence.repository import ConversationRepository

            repo = ConversationRepository(session)
            conv = await repo.get_conversation_for_agent(
                conversation_id, agent_name, workspace_name
            )
            if conv is None:
                raise NotFoundError("conversation", str(conversation_id))

            template = self._get_template(workspace_name, agent_name)
            clone = template.clone()
            clone.conversation_id = conversation_id  # lazy history reload on first run
            self._pool.put(workspace_name, agent_name, conversation_id, clone)
            return clone, conversation_id

        # New conversation
        template = self._get_template(workspace_name, agent_name)
        clone = template.clone()
        if session is not None:
            new_id = await clone.start_conversation(session, workspace_name)
        else:
            new_id = uuid.uuid4()
            clone._conversation_id = new_id
            clone._history_loaded = True
            clone._history = []
        self._pool.put(workspace_name, agent_name, new_id, clone)
        return clone, new_id

    def reset_conversation(
        self, workspace_name: str, agent_name: str, conversation_id: uuid.UUID
    ) -> None:
        """Evict the clone from the pool. DB rows are kept."""
        self._pool.evict(workspace_name, agent_name, conversation_id)

    def _get_template(self, workspace_name: str, agent_name: str) -> Agent:
        ws = self._orchestrator.get_workspace(workspace_name)
        if ws is None:
            raise NotFoundError("workspace", workspace_name)
        agent = ws.get_agent(agent_name)
        if agent is None:
            raise NotFoundError("agent", agent_name)
        return agent
