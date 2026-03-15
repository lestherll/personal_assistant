"""Functional test fixtures.

Overrides ``http_client`` to mock LLM-calling service methods so that
functional tests never make real AI API calls.  Handles JWT auth by
registering a dedicated test user and including the token in every request.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import httpx
import pytest

# Unique per-session suffix so each test run gets a fresh user with no
# leftover DB state from previous runs.
_SESSION_ID = uuid.uuid4().hex[:8]
_TEST_USERNAME = f"func_{_SESSION_ID}"
_TEST_EMAIL = f"func_{_SESSION_ID}@test.com"
_TEST_PASSWORD = "functest_pw_123!"


@pytest.fixture(scope="session")
async def _auth_token(live_server_url: str) -> str:
    """Register a fresh test user for this session and return an access token.

    Returns an empty string when AUTH_DISABLED=true so tests that run
    without a database are unaffected.
    """
    if os.environ.get("AUTH_DISABLED", "").lower() == "true":
        return ""

    async with httpx.AsyncClient(base_url=live_server_url) as client:
        await client.post(
            "/auth/register",
            json={
                "username": _TEST_USERNAME,
                "email": _TEST_EMAIL,
                "password": _TEST_PASSWORD,
            },
        )
        resp = await client.post(
            "/auth/login",
            data={"username": _TEST_USERNAME, "password": _TEST_PASSWORD},
        )
        return str(resp.json()["access_token"])


@pytest.fixture
async def http_client(live_server_url: str, _auth_token: str) -> AsyncIterator[httpx.AsyncClient]:
    """Pre-configured AsyncClient pointed at the live server.

    Mocks LLM-backed methods on the singleton services so that no real AI API
    calls are made during functional tests.  Evaluation tests use their own
    fixture that does NOT apply these patches.
    """
    from api.main import app

    async def _mock_run_agent(
        user_id: object,
        workspace_name: object,
        agent_name: object,
        message: object,
        *,
        conversation_id: uuid.UUID | None,
        session: object,
    ) -> tuple[str, uuid.UUID]:
        return f"Mock reply from {agent_name}", conversation_id or uuid.uuid4()

    headers = {"Authorization": f"Bearer {_auth_token}"} if _auth_token else {}

    with (
        patch.object(
            app.state.agent_service,
            "run_agent",
            side_effect=_mock_run_agent,
        ),
        patch.object(
            app.state.workspace_service,
            "_route",
            new=AsyncMock(return_value="Assistant"),
        ),
    ):
        async with httpx.AsyncClient(base_url=live_server_url, headers=headers) as client:
            yield client
