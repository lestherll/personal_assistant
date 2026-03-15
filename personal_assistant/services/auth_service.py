from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from personal_assistant.auth.password import hash_password, verify_password
from personal_assistant.auth.tokens import create_access_token, create_refresh_token, decode_token
from personal_assistant.persistence.models import User
from personal_assistant.persistence.user_repository import UserRepository
from personal_assistant.services.exceptions import AlreadyExistsError, AuthError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from personal_assistant.core.orchestrator import Orchestrator
    from personal_assistant.persistence.user_workspace_repository import UserWorkspaceRepository


class AuthService:
    """Service layer for user registration, login, and token management."""

    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def register(
        self,
        username: str,
        email: str,
        password: str,
    ) -> tuple[User, str, str]:
        """Register a new user. Returns (user, access_token, refresh_token)."""
        if await self._user_repo.get_by_username(username) is not None:
            raise AlreadyExistsError("user", username)
        if await self._user_repo.get_by_email(email) is not None:
            raise AlreadyExistsError("user", email)

        hashed = hash_password(password)
        user = await self._user_repo.create(username, email, hashed)
        access_token = create_access_token(str(user.id))
        refresh_token = create_refresh_token(str(user.id))
        return user, access_token, refresh_token

    async def login(self, username: str, password: str) -> tuple[User, str, str]:
        """Authenticate a user. Returns (user, access_token, refresh_token)."""
        user = await self._user_repo.get_by_username(username)
        if user is None or not verify_password(password, user.hashed_password):
            raise AuthError("Invalid username or password")
        if not user.is_active:
            raise AuthError("Account is inactive")
        access_token = create_access_token(str(user.id))
        refresh_token = create_refresh_token(str(user.id))
        return user, access_token, refresh_token

    async def refresh(self, refresh_token: str) -> str:
        """Issue a new access token from a valid refresh token."""
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise AuthError("Invalid token type")
        sub = payload.get("sub")
        if not isinstance(sub, str):
            raise AuthError("Invalid token subject")
        return create_access_token(sub)

    async def get_user_from_token(self, token: str, session: AsyncSession) -> User:
        """Resolve a User from an access token. Raises AuthError if invalid."""
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise AuthError("Invalid token type")
        sub = payload.get("sub")
        if not isinstance(sub, str):
            raise AuthError("Invalid token subject")
        try:
            user_id = uuid.UUID(sub)
        except ValueError as exc:
            raise AuthError("Invalid token subject") from exc

        repo = UserRepository(session)
        user = await repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise AuthError("User not found or inactive")
        return user


async def fork_default_workspace(
    user_id: uuid.UUID,
    default_orchestrator: Orchestrator,
    user_workspace_repo: UserWorkspaceRepository,
) -> None:
    """Copy the default workspace's agents into the user's workspace DB rows."""
    default_ws = default_orchestrator.get_workspace("default")
    if default_ws is None:
        return

    ws_row = await user_workspace_repo.upsert_workspace(
        user_id, default_ws.config.name, default_ws.config.description
    )

    for agent_name in default_ws.list_agents():
        agent = default_ws.get_agent(agent_name)
        if agent is None:
            continue
        await user_workspace_repo.upsert_agent(
            ws_row.id,
            agent.config.name,
            agent.config.description,
            agent.config.system_prompt,
            agent.config.provider,
            agent.config.model,
            [t.name for t in agent._tools],
        )
