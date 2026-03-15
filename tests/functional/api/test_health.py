"""Functional tests for GET /health.

These tests start a real Uvicorn server on a random port and make actual
HTTP requests via httpx — no ASGI transport shortcut.
"""

from __future__ import annotations

import httpx


async def test_health_returns_200(http_client: httpx.AsyncClient) -> None:
    response = await http_client.get("/health")

    assert response.status_code == 200


async def test_health_response_body(http_client: httpx.AsyncClient) -> None:
    response = await http_client.get("/health")

    assert response.json()["status"] == "ok"


async def test_health_content_type(http_client: httpx.AsyncClient) -> None:
    response = await http_client.get("/health")

    assert "application/json" in response.headers["content-type"]
