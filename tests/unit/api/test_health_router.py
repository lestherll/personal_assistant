"""Unit tests for api/routers/health.py."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from api.routers import health


def make_app(session_factory: object) -> FastAPI:
    app = FastAPI()
    app.include_router(health.router)
    app.state.session_factory = session_factory
    return app


@pytest.fixture
async def healthy_client() -> AsyncIterator[httpx.AsyncClient]:
    """Client where DB session executes SELECT 1 successfully."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    app = make_app(mock_factory)
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
async def no_db_client() -> AsyncIterator[httpx.AsyncClient]:
    """Client where session_factory is None (dev/no-DB mode)."""
    app = make_app(None)
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
async def error_db_client() -> AsyncIterator[httpx.AsyncClient]:
    """Client where DB raises on execute."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=Exception("connection refused"))
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    app = make_app(mock_factory)
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# DB healthy
# ---------------------------------------------------------------------------


async def test_health_db_ok_returns_200(healthy_client: httpx.AsyncClient) -> None:
    response = await healthy_client.get("/health")
    assert response.status_code == 200


async def test_health_db_ok_overall_status(healthy_client: httpx.AsyncClient) -> None:
    response = await healthy_client.get("/health")
    assert response.json()["status"] == "ok"


async def test_health_db_ok_database_component(healthy_client: httpx.AsyncClient) -> None:
    response = await healthy_client.get("/health")
    data = response.json()
    assert data["components"]["database"]["status"] == "ok"


async def test_health_db_ok_latency_present(healthy_client: httpx.AsyncClient) -> None:
    response = await healthy_client.get("/health")
    data = response.json()
    assert isinstance(data["latency_ms"], float)
    assert data["latency_ms"] >= 0


async def test_health_db_ok_database_latency_present(healthy_client: httpx.AsyncClient) -> None:
    response = await healthy_client.get("/health")
    data = response.json()
    db = data["components"]["database"]
    assert db["latency_ms"] is not None
    assert isinstance(db["latency_ms"], float)


# ---------------------------------------------------------------------------
# No DB (session_factory is None)
# ---------------------------------------------------------------------------


async def test_health_no_db_returns_200(no_db_client: httpx.AsyncClient) -> None:
    response = await no_db_client.get("/health")
    assert response.status_code == 200


async def test_health_no_db_overall_status_degraded(no_db_client: httpx.AsyncClient) -> None:
    response = await no_db_client.get("/health")
    assert response.json()["status"] == "degraded"


async def test_health_no_db_database_unavailable(no_db_client: httpx.AsyncClient) -> None:
    response = await no_db_client.get("/health")
    data = response.json()
    assert data["components"]["database"]["status"] == "unavailable"


async def test_health_no_db_database_latency_none(no_db_client: httpx.AsyncClient) -> None:
    response = await no_db_client.get("/health")
    data = response.json()
    assert data["components"]["database"]["latency_ms"] is None


# ---------------------------------------------------------------------------
# DB error on execute
# ---------------------------------------------------------------------------


async def test_health_db_error_returns_200(error_db_client: httpx.AsyncClient) -> None:
    response = await error_db_client.get("/health")
    assert response.status_code == 200


async def test_health_db_error_overall_status_unhealthy(
    error_db_client: httpx.AsyncClient,
) -> None:
    response = await error_db_client.get("/health")
    assert response.json()["status"] == "unhealthy"


async def test_health_db_error_database_error(error_db_client: httpx.AsyncClient) -> None:
    response = await error_db_client.get("/health")
    data = response.json()
    assert data["components"]["database"]["status"] == "error"
