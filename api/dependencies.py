from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any, cast

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from personal_assistant.config import Settings, get_settings
from personal_assistant.persistence.models import User
from personal_assistant.persistence.user_repository import UserRepository
from personal_assistant.providers.registry import ProviderRegistry
from personal_assistant.services.agent_service import AgentService
from personal_assistant.services.auth_service import AuthService
from personal_assistant.services.exceptions import AuthError
from personal_assistant.services.workspace_service import WorkspaceService

SettingsDep = Annotated[Settings, Depends(get_settings)]

DEV_USER = User(
    id=uuid.UUID(int=0),
    username="dev",
    email="dev@local",
    hashed_password="",  # nosec B106 — dev-mode sentinel, no real password
    is_active=True,
    created_at=datetime.now(UTC),
    updated_at=datetime.now(UTC),
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_orchestrator(request: Request) -> Any:
    """Return the application-scoped template Orchestrator stored on app.state."""
    return request.app.state.orchestrator


def get_provider_registry(request: Request) -> ProviderRegistry:
    """Return the application-scoped ProviderRegistry from app.state."""
    return cast(ProviderRegistry, get_orchestrator(request).registry)


def get_agent_service(request: Request) -> AgentService:
    """Return the application-scoped AgentService singleton from app.state."""
    return cast(AgentService, request.app.state.agent_service)


def get_workspace_service(request: Request) -> WorkspaceService:
    """Return the application-scoped WorkspaceService singleton from app.state."""
    return cast(WorkspaceService, request.app.state.workspace_service)


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
    if get_settings().auth_disabled:
        return DEV_USER
    if token is None:
        raise AuthError("No authentication token provided")
    if session is None:
        raise AuthError("Database unavailable")
    auth_service = AuthService(UserRepository(session))
    return await auth_service.get_user_from_token(token, session)


CurrentUserDep = Annotated[User, Depends(get_current_user)]
