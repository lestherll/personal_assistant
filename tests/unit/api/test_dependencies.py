"""Unit tests for api.dependencies."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.dependencies import (
    DEV_USER,
    get_agent_service,
    get_current_user,
    get_workspace_service,
)
from personal_assistant.auth.api_keys import generate_api_key
from personal_assistant.persistence.models import User, UserAPIKey
from personal_assistant.services.agent_service import AgentService
from personal_assistant.services.exceptions import AuthError
from personal_assistant.services.workspace_service import WorkspaceService


def _make_request(agent_service=None, workspace_service=None) -> MagicMock:
    request = MagicMock()
    request.app.state.agent_service = agent_service or MagicMock(spec=AgentService)
    request.app.state.workspace_service = workspace_service or MagicMock(spec=WorkspaceService)
    return request


# ---------------------------------------------------------------------------
# get_workspace_service
# ---------------------------------------------------------------------------


def test_get_workspace_service_returns_singleton_from_app_state():
    svc = MagicMock(spec=WorkspaceService)
    request = _make_request(workspace_service=svc)
    result = get_workspace_service(request)
    assert result is svc


def test_get_workspace_service_identity_is_preserved():
    svc = MagicMock(spec=WorkspaceService)
    request_a = _make_request(workspace_service=svc)
    request_b = _make_request(workspace_service=svc)
    assert get_workspace_service(request_a) is get_workspace_service(request_b)


# ---------------------------------------------------------------------------
# get_agent_service
# ---------------------------------------------------------------------------


def test_get_agent_service_returns_singleton_from_app_state():
    svc = MagicMock(spec=AgentService)
    request = _make_request(agent_service=svc)
    result = get_agent_service(request)
    assert result is svc


def test_get_agent_service_identity_is_preserved():
    svc = MagicMock(spec=AgentService)
    request_a = _make_request(agent_service=svc)
    request_b = _make_request(agent_service=svc)
    assert get_agent_service(request_a) is get_agent_service(request_b)


# ---------------------------------------------------------------------------
# DEV_USER sentinel
# ---------------------------------------------------------------------------


def test_dev_user_has_zero_uuid():
    assert DEV_USER.id == uuid.UUID(int=0)


# ---------------------------------------------------------------------------
# get_current_user — API key path
# ---------------------------------------------------------------------------


def _make_user(user_id: uuid.UUID | None = None) -> User:
    return User(
        id=user_id or uuid.uuid4(),
        username="testuser",
        email="test@test.com",
        hashed_password="",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _make_api_key_row(
    user_id: uuid.UUID,
    key_hash: str,
    *,
    is_active: bool = True,
    expires_at: datetime | None = None,
) -> MagicMock:
    row = MagicMock(spec=UserAPIKey)
    row.id = uuid.uuid4()
    row.user_id = user_id
    row.name = "test-key"
    row.key_hash = key_hash
    row.key_prefix = "sk-test1234"
    row.is_active = is_active
    row.expires_at = expires_at
    row.last_used_at = None
    row.created_at = datetime.now(UTC)
    return row


class TestGetCurrentUserApiKey:
    @pytest.mark.asyncio
    async def test_valid_api_key_returns_user(self):
        raw_key, key_hash = generate_api_key()
        user = _make_user()
        api_key_row = _make_api_key_row(user.id, key_hash)
        session = AsyncMock()

        with (
            patch("api.dependencies.APIKeyRepository") as MockRepo,
            patch("api.dependencies.UserRepository") as MockUserRepo,
            patch("api.dependencies.get_settings") as mock_settings,
        ):
            mock_settings.return_value.auth_disabled = False
            MockRepo.return_value.get_by_hash = AsyncMock(return_value=api_key_row)
            MockRepo.return_value.update_last_used = AsyncMock()
            MockUserRepo.return_value.get_by_id = AsyncMock(return_value=user)

            result = await get_current_user(raw_key, session)
            assert result is user

    @pytest.mark.asyncio
    async def test_invalid_api_key_raises(self):
        session = AsyncMock()

        with (
            patch("api.dependencies.APIKeyRepository") as MockRepo,
            patch("api.dependencies.get_settings") as mock_settings,
        ):
            mock_settings.return_value.auth_disabled = False
            MockRepo.return_value.get_by_hash = AsyncMock(return_value=None)

            with pytest.raises(AuthError, match="Invalid API key"):
                await get_current_user("sk-nonexistent", session)

    @pytest.mark.asyncio
    async def test_revoked_api_key_raises(self):
        raw_key, key_hash = generate_api_key()
        api_key_row = _make_api_key_row(uuid.uuid4(), key_hash, is_active=False)
        session = AsyncMock()

        with (
            patch("api.dependencies.APIKeyRepository") as MockRepo,
            patch("api.dependencies.get_settings") as mock_settings,
        ):
            mock_settings.return_value.auth_disabled = False
            MockRepo.return_value.get_by_hash = AsyncMock(return_value=api_key_row)

            with pytest.raises(AuthError, match="revoked"):
                await get_current_user(raw_key, session)

    @pytest.mark.asyncio
    async def test_expired_api_key_raises(self):
        raw_key, key_hash = generate_api_key()
        expired = datetime.now(UTC) - timedelta(days=1)
        api_key_row = _make_api_key_row(uuid.uuid4(), key_hash, expires_at=expired)
        session = AsyncMock()

        with (
            patch("api.dependencies.APIKeyRepository") as MockRepo,
            patch("api.dependencies.get_settings") as mock_settings,
        ):
            mock_settings.return_value.auth_disabled = False
            MockRepo.return_value.get_by_hash = AsyncMock(return_value=api_key_row)

            with pytest.raises(AuthError, match="expired"):
                await get_current_user(raw_key, session)
