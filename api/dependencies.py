from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.persistence.models import User
from personal_assistant.persistence.user_repository import UserRepository
from personal_assistant.persistence.user_workspace_repository import UserWorkspaceRepository
from personal_assistant.providers.registry import ProviderRegistry
from personal_assistant.services.agent_service import AgentService
from personal_assistant.services.auth_service import AuthService
from personal_assistant.services.conversation_pool import ConversationPool
from personal_assistant.services.conversation_service import ConversationService
from personal_assistant.services.exceptions import AuthError
from personal_assistant.services.user_orchestrator_registry import UserOrchestratorRegistry
from personal_assistant.services.workspace_service import WorkspaceService

AUTH_DISABLED = os.getenv("AUTH_DISABLED", "false").lower() == "true"

DEV_USER = User(
    id=uuid.UUID(int=0),
    username="dev",
    email="dev@local",
    hashed_password="",
    is_active=True,
    created_at=datetime.now(UTC),
    updated_at=datetime.now(UTC),
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_orchestrator(request: Request) -> Orchestrator:
    """Return the application-scoped (template) Orchestrator stored on app.state."""
    return cast(Orchestrator, request.app.state.orchestrator)


def get_conversation_pool(request: Request) -> ConversationPool:
    """Return the application-scoped ConversationPool stored on app.state."""
    return cast(ConversationPool, request.app.state.conversation_pool)


def get_provider_registry(request: Request) -> ProviderRegistry:
    """Return the application-scoped ProviderRegistry from the orchestrator."""
    return cast(Orchestrator, request.app.state.orchestrator).registry


def get_user_orchestrator_registry(request: Request) -> UserOrchestratorRegistry:
    """Return the application-scoped UserOrchestratorRegistry from app.state."""
    return cast(UserOrchestratorRegistry, request.app.state.user_orchestrators)


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession | None]:
    """Yield an AsyncSession if a session factory is configured, otherwise None."""
    factory: async_sessionmaker[AsyncSession] | None = request.app.state.session_factory
    if factory is None:
        yield None
        return
    async with factory() as session:
        yield session


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession | None, Depends(get_db_session)],
) -> User:
    """Return the current user from the JWT token, or the dev sentinel when AUTH_DISABLED."""
    if AUTH_DISABLED:
        return DEV_USER
    if token is None:
        raise AuthError("No authentication token provided")
    if session is None:
        raise AuthError("Database unavailable")
    auth_service = AuthService(UserRepository(session))
    return await auth_service.get_user_from_token(token, session)


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def get_user_orchestrator(
    request: Request,
    current_user: CurrentUserDep,
    session: Annotated[AsyncSession | None, Depends(get_db_session)],
) -> Orchestrator:
    """Return the orchestrator for the current user.

    Falls back to the template orchestrator in dev/no-DB mode.
    """
    registry = get_user_orchestrator_registry(request)

    # Fast path: cached orchestrator
    cached = registry.get(current_user.id)
    if cached is not None:
        return cached

    # No DB — use template orchestrator (dev mode or fallback)
    if session is None:
        return cast(Orchestrator, request.app.state.orchestrator)

    # Build user orchestrator from DB rows
    ws_repo = UserWorkspaceRepository(session)
    ws_rows = await ws_repo.list_workspaces(current_user.id)
    user_agent_rows = {}
    for ws_row in ws_rows:
        user_agent_rows[ws_row.id] = await ws_repo.list_agents(ws_row.id)

    return registry.build_and_cache(current_user.id, ws_rows, user_agent_rows)


UserOrchestratorDep = Annotated[Orchestrator, Depends(get_user_orchestrator)]


def get_conversation_service(
    orchestrator: UserOrchestratorDep,
    pool: Annotated[ConversationPool, Depends(get_conversation_pool)],
) -> ConversationService:
    """Return a request-scoped ConversationService using the user's orchestrator."""
    return ConversationService(orchestrator, pool)


def get_workspace_service(
    orchestrator: UserOrchestratorDep,
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> WorkspaceService:
    """Return a request-scoped WorkspaceService wrapping the user's orchestrator."""
    return WorkspaceService(orchestrator, conversation_service)


def get_agent_service(
    orchestrator: UserOrchestratorDep,
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> AgentService:
    """Return a request-scoped AgentService wrapping the user's orchestrator."""
    return AgentService(orchestrator, conversation_service)
