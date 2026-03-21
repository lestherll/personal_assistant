"""Functional tests for /auth/me endpoint."""

from __future__ import annotations

import os

import httpx
import pytest

_AUTH_DISABLED = os.environ.get("AUTH_DISABLED", "").lower() == "true"


async def test_get_me_authenticated(http_client: httpx.AsyncClient) -> None:
    response = await http_client.get("/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert "id" in body
    assert "username" in body
    assert "email" in body
    assert "created_at" in body


@pytest.mark.skipif(_AUTH_DISABLED, reason="AUTH_DISABLED=true bypasses all auth checks")
async def test_get_me_unauthenticated(live_server_url: str) -> None:
    async with httpx.AsyncClient(base_url=live_server_url) as client:
        response = await client.get("/auth/me")

    assert response.status_code == 401


@pytest.mark.skipif(_AUTH_DISABLED, reason="AUTH_DISABLED=true bypasses all auth checks")
async def test_get_me_invalid_token(live_server_url: str) -> None:
    async with httpx.AsyncClient(
        base_url=live_server_url,
        headers={"Authorization": "Bearer not-a-real-token"},
    ) as client:
        response = await client.get("/auth/me")

    assert response.status_code == 401
