from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from personal_assistant.persistence.models import UserAgent, UserWorkspace


class UserWorkspaceRepository:
    """Data-access layer for UserWorkspace and UserAgent records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Workspaces
    # ------------------------------------------------------------------

    async def create_workspace(
        self, user_id: uuid.UUID, name: str, description: str
    ) -> UserWorkspace:
        ws = UserWorkspace(user_id=user_id, name=name, description=description)
        self._session.add(ws)
        await self._session.commit()
        await self._session.refresh(ws)
        return ws

    async def get_workspace(self, user_id: uuid.UUID, name: str) -> UserWorkspace | None:
        result = await self._session.execute(
            select(UserWorkspace).where(
                UserWorkspace.user_id == user_id, UserWorkspace.name == name
            )
        )
        return result.scalar_one_or_none()

    async def list_workspaces(self, user_id: uuid.UUID) -> list[UserWorkspace]:
        result = await self._session.execute(
            select(UserWorkspace).where(UserWorkspace.user_id == user_id)
        )
        return list(result.scalars().all())

    async def delete_workspace(self, user_id: uuid.UUID, name: str) -> bool:
        ws = await self.get_workspace(user_id, name)
        if ws is None:
            return False
        await self._session.delete(ws)
        await self._session.commit()
        return True

    async def upsert_workspace(
        self, user_id: uuid.UUID, name: str, description: str
    ) -> UserWorkspace:
        ws = await self.get_workspace(user_id, name)
        if ws is None:
            return await self.create_workspace(user_id, name, description)
        ws.description = description
        await self._session.commit()
        await self._session.refresh(ws)
        return ws

    # ------------------------------------------------------------------
    # Agents
    # ------------------------------------------------------------------

    async def create_agent(
        self,
        user_workspace_id: uuid.UUID,
        name: str,
        description: str,
        system_prompt: str,
        provider: str | None,
        model: str | None,
        allowed_tools: list[str] | None,
    ) -> UserAgent:
        agent = UserAgent(
            user_workspace_id=user_workspace_id,
            name=name,
            description=description,
            system_prompt=system_prompt,
            provider=provider,
            model=model,
            allowed_tools=allowed_tools,
        )
        self._session.add(agent)
        await self._session.commit()
        await self._session.refresh(agent)
        return agent

    async def get_agent(self, user_workspace_id: uuid.UUID, name: str) -> UserAgent | None:
        result = await self._session.execute(
            select(UserAgent).where(
                UserAgent.user_workspace_id == user_workspace_id, UserAgent.name == name
            )
        )
        return result.scalar_one_or_none()

    async def list_agents(self, user_workspace_id: uuid.UUID) -> list[UserAgent]:
        result = await self._session.execute(
            select(UserAgent).where(UserAgent.user_workspace_id == user_workspace_id)
        )
        return list(result.scalars().all())

    async def delete_agent(self, user_workspace_id: uuid.UUID, name: str) -> bool:
        agent = await self.get_agent(user_workspace_id, name)
        if agent is None:
            return False
        await self._session.delete(agent)
        await self._session.commit()
        return True

    async def upsert_agent(
        self,
        user_workspace_id: uuid.UUID,
        name: str,
        description: str,
        system_prompt: str,
        provider: str | None,
        model: str | None,
        allowed_tools: list[str] | None,
    ) -> UserAgent:
        agent = await self.get_agent(user_workspace_id, name)
        if agent is None:
            return await self.create_agent(
                user_workspace_id, name, description, system_prompt, provider, model, allowed_tools
            )
        agent.description = description
        agent.system_prompt = system_prompt
        agent.provider = provider
        agent.model = model
        agent.allowed_tools = allowed_tools
        await self._session.commit()
        await self._session.refresh(agent)
        return agent
