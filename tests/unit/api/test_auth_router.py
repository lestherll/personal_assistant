"""Unit tests for the /auth router."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from api.dependencies import get_current_user, get_db_session
from api.exception_handlers import register_exception_handlers
from api.routers import auth
from personal_assistant.persistence.models import User, UserAPIKey
from personal_assistant.services.auth_service import AuthService
from personal_assistant.services.exceptions import AlreadyExistsError, AuthError


def _make_user(username: str = "alice") -> User:
    return User(
        id=uuid.uuid4(),
        username=username,
        email=f"{username}@example.com",
        hashed_password="hashed",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_orchestrator() -> MagicMock:
    return MagicMock()


@pytest.fixture
async def auth_client(
    mock_session: MagicMock, mock_orchestrator: MagicMock
) -> AsyncIterator[httpx.AsyncClient]:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(auth.router)
    app.state.orchestrator = mock_orchestrator
    app.dependency_overrides[get_db_session] = lambda: mock_session
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------


class TestRegisterEndpoint:
    async def test_register_success(
        self,
        auth_client: httpx.AsyncClient,
        mock_session: MagicMock,
        mock_orchestrator: MagicMock,
    ) -> None:
        user = _make_user()
        fork_mock = AsyncMock()
        with (
            _patch_auth_service("register", return_value=(user, "access_tok", "refresh_tok")),
            patch(
                "api.routers.auth.fork_default_workspace",
                fork_mock,
            ),
        ):
            resp = await auth_client.post(
                "/auth/register",
                json={"username": "alice", "email": "alice@example.com", "password": "pw"},
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["user"]["username"] == "alice"
        assert data["tokens"]["access_token"] == "access_tok"
        fork_mock.assert_awaited_once()
        call_args = fork_mock.call_args
        assert call_args.kwargs["user_id"] == user.id or call_args.args[0] == user.id

    async def test_duplicate_user_returns_409(self, auth_client: httpx.AsyncClient) -> None:
        with _patch_auth_service("register", side_effect=AlreadyExistsError("user", "alice")):
            resp = await auth_client.post(
                "/auth/register",
                json={"username": "alice", "email": "alice@example.com", "password": "pw"},
            )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


class TestLoginEndpoint:
    async def test_login_success(self, auth_client: httpx.AsyncClient) -> None:
        user = _make_user()
        with _patch_auth_service("login", return_value=(user, "acc", "ref")):
            resp = await auth_client.post(
                "/auth/login", data={"username": "alice", "password": "secret"}
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "acc"

    async def test_bad_credentials_returns_401(self, auth_client: httpx.AsyncClient) -> None:
        with _patch_auth_service("login", side_effect=AuthError("Invalid credentials")):
            resp = await auth_client.post(
                "/auth/login", data={"username": "alice", "password": "wrong"}
            )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------


class TestRefreshEndpoint:
    async def test_refresh_success(self, auth_client: httpx.AsyncClient) -> None:
        with _patch_auth_service("refresh", return_value="new_access"):
            resp = await auth_client.post("/auth/refresh", json={"refresh_token": "some_refresh"})
        assert resp.status_code == 200
        assert resp.json()["access_token"] == "new_access"

    async def test_invalid_refresh_returns_401(self, auth_client: httpx.AsyncClient) -> None:
        with _patch_auth_service("refresh", side_effect=AuthError("Invalid")):
            resp = await auth_client.post("/auth/refresh", json={"refresh_token": "bad"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_auth_service(method: str, **kwargs: object):  # type: ignore[no-untyped-def]
    """Patch AuthService.<method> on the module level."""
    from unittest.mock import patch

    mock = AsyncMock(**kwargs)
    return patch.object(AuthService, method, mock)


# ---------------------------------------------------------------------------
# API key endpoint fixtures
# ---------------------------------------------------------------------------

_DEV_USER = _make_user("dev")


@pytest.fixture
async def api_key_client(
    mock_session: MagicMock, mock_orchestrator: MagicMock
) -> AsyncIterator[httpx.AsyncClient]:
    """Auth client with get_current_user overridden so API key endpoints work."""
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(auth.router)
    app.state.orchestrator = mock_orchestrator
    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_current_user] = lambda: _DEV_USER
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


def _make_api_key_row(user_id: uuid.UUID, **overrides: object) -> MagicMock:
    row = MagicMock(spec=UserAPIKey)
    row.id = uuid.uuid4()
    row.user_id = user_id
    row.name = "my-key"
    row.key_hash = "abc123"
    row.key_prefix = "sk-test1234"
    row.is_active = True
    row.expires_at = None
    row.last_used_at = None
    row.created_at = datetime.now(UTC)
    for k, v in overrides.items():
        setattr(row, k, v)
    return row


# ---------------------------------------------------------------------------
# POST /auth/api-keys
# ---------------------------------------------------------------------------


class TestCreateApiKeyEndpoint:
    async def test_create_api_key_returns_201(self, api_key_client: httpx.AsyncClient) -> None:
        row = _make_api_key_row(_DEV_USER.id)
        with patch("api.routers.auth.APIKeyRepository") as MockRepo:
            MockRepo.return_value.create = AsyncMock(return_value=row)
            resp = await api_key_client.post("/auth/api-keys", json={"name": "my-key"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["key"].startswith("sk-")
        assert data["api_key"]["name"] == "my-key"

    async def test_create_api_key_response_shape(self, api_key_client: httpx.AsyncClient) -> None:
        row = _make_api_key_row(_DEV_USER.id)
        with patch("api.routers.auth.APIKeyRepository") as MockRepo:
            MockRepo.return_value.create = AsyncMock(return_value=row)
            resp = await api_key_client.post("/auth/api-keys", json={"name": "test"})
        data = resp.json()
        assert "key" in data
        api_key = data["api_key"]
        assert "id" in api_key
        assert "key_prefix" in api_key
        assert "is_active" in api_key
        assert "created_at" in api_key


# ---------------------------------------------------------------------------
# GET /auth/api-keys
# ---------------------------------------------------------------------------


class TestListApiKeysEndpoint:
    async def test_list_api_keys_returns_200(self, api_key_client: httpx.AsyncClient) -> None:
        rows = [_make_api_key_row(_DEV_USER.id), _make_api_key_row(_DEV_USER.id, name="second")]
        with patch("api.routers.auth.APIKeyRepository") as MockRepo:
            MockRepo.return_value.list_for_user = AsyncMock(return_value=rows)
            resp = await api_key_client.get("/auth/api-keys")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_list_api_keys_empty(self, api_key_client: httpx.AsyncClient) -> None:
        with patch("api.routers.auth.APIKeyRepository") as MockRepo:
            MockRepo.return_value.list_for_user = AsyncMock(return_value=[])
            resp = await api_key_client.get("/auth/api-keys")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# DELETE /auth/api-keys/{key_id}
# ---------------------------------------------------------------------------


class TestRevokeApiKeyEndpoint:
    async def test_revoke_returns_204(self, api_key_client: httpx.AsyncClient) -> None:
        key_id = uuid.uuid4()
        with patch("api.routers.auth.APIKeyRepository") as MockRepo:
            MockRepo.return_value.revoke = AsyncMock(return_value=True)
            resp = await api_key_client.delete(f"/auth/api-keys/{key_id}")
        assert resp.status_code == 204

    async def test_revoke_not_found_returns_404(self, api_key_client: httpx.AsyncClient) -> None:
        key_id = uuid.uuid4()
        with patch("api.routers.auth.APIKeyRepository") as MockRepo:
            MockRepo.return_value.revoke = AsyncMock(return_value=False)
            resp = await api_key_client.delete(f"/auth/api-keys/{key_id}")
        assert resp.status_code == 404
