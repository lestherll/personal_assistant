from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.providers.registry import ProviderRegistry
from personal_assistant.services.agent_service import AgentService
from personal_assistant.services.conversation_pool import ConversationPool
from personal_assistant.services.conversation_service import ConversationService
from personal_assistant.services.workspace_service import WorkspaceService


def get_orchestrator(request: Request) -> Orchestrator:
    """Return the application-scoped Orchestrator stored on app.state."""
    return cast(Orchestrator, request.app.state.orchestrator)


def get_conversation_pool(request: Request) -> ConversationPool:
    """Return the application-scoped ConversationPool stored on app.state."""
    return cast(ConversationPool, request.app.state.conversation_pool)


def get_provider_registry(request: Request) -> ProviderRegistry:
    """Return the application-scoped ProviderRegistry from the orchestrator."""
    return cast(Orchestrator, request.app.state.orchestrator).registry


def get_workspace_service(
    orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> WorkspaceService:
    """Return a request-scoped WorkspaceService wrapping the orchestrator."""
    return WorkspaceService(orchestrator, conversation_service)


def get_conversation_service(
    orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
    pool: Annotated[ConversationPool, Depends(get_conversation_pool)],
) -> ConversationService:
    """Return a request-scoped ConversationService."""
    return ConversationService(orchestrator, pool)


def get_agent_service(
    orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> AgentService:
    """Return a request-scoped AgentService wrapping the orchestrator."""
    return AgentService(orchestrator, conversation_service)


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession | None]:
    """Yield an AsyncSession if a session factory is configured, otherwise None."""
    factory: async_sessionmaker[AsyncSession] | None = request.app.state.session_factory
    if factory is None:
        yield None
        return
    async with factory() as session:
        yield session
