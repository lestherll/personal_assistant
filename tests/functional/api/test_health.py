"""Functional tests for GET /health.

These tests start a real Uvicorn server on a random port and make actual
HTTP requests via httpx — no ASGI transport shortcut.
"""

from __future__ import annotations

import httpx


async def test_health_returns_200(live_server_url: str) -> None:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{live_server_url}/health")

    assert response.status_code == 200


async def test_health_response_body(live_server_url: str) -> None:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{live_server_url}/health")

    assert response.json() == {"status": "ok"}


async def test_health_content_type(live_server_url: str) -> None:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{live_server_url}/health")

    assert "application/json" in response.headers["content-type"]
