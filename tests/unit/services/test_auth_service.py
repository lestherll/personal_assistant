"""Unit tests for AuthService."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from personal_assistant.auth.password import hash_password
from personal_assistant.persistence.models import User
from personal_assistant.persistence.user_repository import UserRepository
from personal_assistant.services.auth_service import AuthService
from personal_assistant.services.exceptions import AlreadyExistsError, AuthError


def _make_user(username: str = "alice", is_active: bool = True) -> User:
    from datetime import UTC, datetime

    return User(
        id=uuid.uuid4(),
        username=username,
        email=f"{username}@example.com",
        hashed_password=hash_password("secret"),
        is_active=is_active,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_repo() -> MagicMock:
    repo = MagicMock(spec=UserRepository)
    repo.create = AsyncMock()
    repo.get_by_username = AsyncMock(return_value=None)
    repo.get_by_email = AsyncMock(return_value=None)
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def service(mock_repo: MagicMock) -> AuthService:
    return AuthService(mock_repo)


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


class TestRegister:
    async def test_success_returns_user_and_tokens(
        self, service: AuthService, mock_repo: MagicMock
    ) -> None:
        user = _make_user()
        mock_repo.create.return_value = user

        returned_user, access, refresh = await service.register("alice", "alice@example.com", "pw")

        assert returned_user is user
        assert isinstance(access, str)
        assert isinstance(refresh, str)

    async def test_duplicate_username_raises(
        self, service: AuthService, mock_repo: MagicMock
    ) -> None:
        mock_repo.get_by_username.return_value = _make_user()
        with pytest.raises(AlreadyExistsError):
            await service.register("alice", "alice@example.com", "pw")

    async def test_duplicate_email_raises(self, service: AuthService, mock_repo: MagicMock) -> None:
        mock_repo.get_by_email.return_value = _make_user()
        with pytest.raises(AlreadyExistsError):
            await service.register("alice", "alice@example.com", "pw")


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------


class TestLogin:
    async def test_valid_credentials_returns_tokens(
        self, service: AuthService, mock_repo: MagicMock
    ) -> None:
        user = _make_user()
        mock_repo.get_by_username.return_value = user

        returned_user, access, refresh = await service.login("alice", "secret")

        assert returned_user is user
        assert isinstance(access, str)
        assert isinstance(refresh, str)

    async def test_wrong_password_raises_auth_error(
        self, service: AuthService, mock_repo: MagicMock
    ) -> None:
        mock_repo.get_by_username.return_value = _make_user()
        with pytest.raises(AuthError):
            await service.login("alice", "wrong")

    async def test_unknown_user_raises_auth_error(
        self, service: AuthService, mock_repo: MagicMock
    ) -> None:
        mock_repo.get_by_username.return_value = None
        with pytest.raises(AuthError):
            await service.login("ghost", "secret")

    async def test_inactive_user_raises_auth_error(
        self, service: AuthService, mock_repo: MagicMock
    ) -> None:
        mock_repo.get_by_username.return_value = _make_user(is_active=False)
        with pytest.raises(AuthError):
            await service.login("alice", "secret")


# ---------------------------------------------------------------------------
# refresh
# ---------------------------------------------------------------------------


class TestRefresh:
    async def test_valid_refresh_token_returns_new_access_token(self, service: AuthService) -> None:
        from personal_assistant.auth.tokens import create_refresh_token

        refresh = create_refresh_token(str(uuid.uuid4()))
        new_access = await service.refresh(refresh)
        assert isinstance(new_access, str)

    async def test_access_token_rejected_as_refresh(self, service: AuthService) -> None:
        from personal_assistant.auth.tokens import create_access_token

        access = create_access_token(str(uuid.uuid4()))
        with pytest.raises(AuthError):
            await service.refresh(access)

    async def test_invalid_token_raises_auth_error(self, service: AuthService) -> None:
        with pytest.raises(AuthError):
            await service.refresh("not.a.token")


# ---------------------------------------------------------------------------
# get_user_from_token
# ---------------------------------------------------------------------------


class TestGetUserFromToken:
    async def test_valid_token_returns_user(
        self, service: AuthService, mock_repo: MagicMock
    ) -> None:
        from personal_assistant.auth.tokens import create_access_token

        user = _make_user()
        mock_repo.get_by_id.return_value = user
        token = create_access_token(str(user.id))

        # Patch UserRepository inside AuthService
        with patch(
            "personal_assistant.services.auth_service.UserRepository", return_value=mock_repo
        ):
            result = await service.get_user_from_token(token, MagicMock())

        assert result is user

    async def test_refresh_token_rejected(self, service: AuthService, mock_repo: MagicMock) -> None:
        from personal_assistant.auth.tokens import create_refresh_token

        refresh = create_refresh_token(str(uuid.uuid4()))
        with pytest.raises(AuthError):
            await service.get_user_from_token(refresh, MagicMock())

    async def test_user_not_found_raises_auth_error(
        self, service: AuthService, mock_repo: MagicMock
    ) -> None:
        from personal_assistant.auth.tokens import create_access_token

        token = create_access_token(str(uuid.uuid4()))
        mock_repo.get_by_id.return_value = None

        with patch(
            "personal_assistant.services.auth_service.UserRepository", return_value=mock_repo
        ):
            with pytest.raises(AuthError):
                await service.get_user_from_token(token, MagicMock())

    async def test_inactive_user_raises_auth_error(
        self, service: AuthService, mock_repo: MagicMock
    ) -> None:
        from personal_assistant.auth.tokens import create_access_token

        user = _make_user(is_active=False)
        mock_repo.get_by_id.return_value = user
        token = create_access_token(str(user.id))

        with patch(
            "personal_assistant.services.auth_service.UserRepository", return_value=mock_repo
        ):
            with pytest.raises(AuthError):
                await service.get_user_from_token(token, MagicMock())
