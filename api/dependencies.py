from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.services.agent_service import AgentService
from personal_assistant.services.workspace_service import WorkspaceService


def get_orchestrator(request: Request) -> Orchestrator:
    """Return the application-scoped Orchestrator stored on app.state."""
    return cast(Orchestrator, request.app.state.orchestrator)


def get_workspace_service(
    orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
) -> WorkspaceService:
    """Return a request-scoped WorkspaceService wrapping the orchestrator."""
    return WorkspaceService(orchestrator)


def get_agent_service(
    orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
) -> AgentService:
    """Return a request-scoped AgentService wrapping the orchestrator."""
    return AgentService(orchestrator)


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession | None]:
    """Yield an AsyncSession if a session factory is configured, otherwise None."""
    factory: async_sessionmaker[AsyncSession] | None = request.app.state.session_factory
    if factory is None:
        yield None
        return
    async with factory() as session:
        yield session
