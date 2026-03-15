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

from api.dependencies import get_db_session
from api.exception_handlers import register_exception_handlers
from api.routers import auth
from personal_assistant.persistence.models import User
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
def mock_session() -> MagicMock:
    return MagicMock()


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
