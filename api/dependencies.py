from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any, cast

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.rate_limit import RateLimiter
from personal_assistant.auth.api_keys import hash_api_key
from personal_assistant.config import Settings, get_settings
from personal_assistant.persistence.api_key_repository import APIKeyRepository
from personal_assistant.persistence.models import User
from personal_assistant.persistence.user_repository import UserRepository
from personal_assistant.providers.registry import ProviderRegistry
from personal_assistant.services.agent_service import AgentService
from personal_assistant.services.auth_service import AuthService
from personal_assistant.services.exceptions import AuthError
from personal_assistant.services.usage_service import UsageService
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


def get_usage_service(request: Request) -> UsageService:
    """Return the application-scoped UsageService singleton from app.state."""
    return cast(UsageService, request.app.state.usage_service)


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
    request: Request,
) -> User:
    """Return the current user from JWT, API key, or dev sentinel.

    Resolution order:
    1. ``Authorization: Bearer <token>`` header (API clients, API keys)
    2. ``access_token`` httpOnly cookie (browser UI)
    """
    if get_settings().auth_disabled:
        return DEV_USER
    if token is None:
        token = request.cookies.get("access_token")
    if token is None:
        raise AuthError("No authentication token provided")
    if session is None:
        raise AuthError("Database unavailable")

    # API key path: tokens starting with "sk-" are looked up by hash
    if token.startswith("sk-"):
        return await _resolve_api_key_user(token, session)

    # JWT path
    auth_service = AuthService(UserRepository(session))
    return await auth_service.get_user_from_token(token, session)


async def _resolve_api_key_user(key: str, session: AsyncSession) -> User:
    """Validate an API key and return its owner."""
    repo = APIKeyRepository(session)
    key_hash = hash_api_key(key)
    api_key = await repo.get_by_hash(key_hash)
    if api_key is None:
        raise AuthError("Invalid API key")
    if not api_key.is_active:
        raise AuthError("API key has been revoked")
    if api_key.expires_at is not None and api_key.expires_at < datetime.now(UTC):
        raise AuthError("API key has expired")
    # Update last_used_at (best-effort)
    await repo.update_last_used(api_key.id, datetime.now(UTC))
    # Load and return the user
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(api_key.user_id)
    if user is None or not user.is_active:
        raise AuthError("User not found or inactive")
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def get_rate_limiter(request: Request) -> RateLimiter:
    """Return the application-scoped RateLimiter from app.state."""
    return cast(RateLimiter, request.app.state.rate_limiter)


async def rate_limit_chat(
    user: CurrentUserDep,
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> None:
    """FastAPI dependency that enforces per-user rate limits on chat endpoints."""
    limiter.check(user.id)
