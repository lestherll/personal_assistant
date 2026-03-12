"""Unit tests for api.exception_handlers.

Each test wires a minimal FastAPI app with the exception handlers registered,
adds a route that raises the target exception, and verifies the HTTP response.
Uses httpx.AsyncClient with ASGITransport — no real server needed here.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from api.exception_handlers import register_exception_handlers
from personal_assistant.services.exceptions import (
    AlreadyExistsError,
    NotFoundError,
    ServiceValidationError,
)


@pytest.fixture
def exc_app() -> FastAPI:
    """Minimal app with exception handlers and one route per exception type."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/raise/not-found")
    async def raise_not_found() -> None:
        raise NotFoundError("workspace", "missing")

    @app.get("/raise/already-exists")
    async def raise_already_exists() -> None:
        raise AlreadyExistsError("agent", "duplicate")

    @app.get("/raise/validation-error")
    async def raise_validation_error() -> None:
        raise ServiceValidationError("bad input")

    return app


# ---------------------------------------------------------------------------
# NotFoundError → 404
# ---------------------------------------------------------------------------


async def test_not_found_status_code(exc_app: FastAPI) -> None:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=exc_app), base_url="http://test"
    ) as client:
        response = await client.get("/raise/not-found")

    assert response.status_code == 404


async def test_not_found_error_field(exc_app: FastAPI) -> None:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=exc_app), base_url="http://test"
    ) as client:
        response = await client.get("/raise/not-found")

    assert response.json()["error"] == "not_found"


async def test_not_found_detail_contains_message(exc_app: FastAPI) -> None:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=exc_app), base_url="http://test"
    ) as client:
        response = await client.get("/raise/not-found")

    assert "missing" in response.json()["detail"]


# ---------------------------------------------------------------------------
# AlreadyExistsError → 409
# ---------------------------------------------------------------------------


async def test_already_exists_status_code(exc_app: FastAPI) -> None:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=exc_app), base_url="http://test"
    ) as client:
        response = await client.get("/raise/already-exists")

    assert response.status_code == 409


async def test_already_exists_error_field(exc_app: FastAPI) -> None:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=exc_app), base_url="http://test"
    ) as client:
        response = await client.get("/raise/already-exists")

    assert response.json()["error"] == "already_exists"


async def test_already_exists_detail_contains_message(exc_app: FastAPI) -> None:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=exc_app), base_url="http://test"
    ) as client:
        response = await client.get("/raise/already-exists")

    assert "duplicate" in response.json()["detail"]


# ---------------------------------------------------------------------------
# ServiceValidationError → 422
# ---------------------------------------------------------------------------


async def test_validation_error_status_code(exc_app: FastAPI) -> None:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=exc_app), base_url="http://test"
    ) as client:
        response = await client.get("/raise/validation-error")

    assert response.status_code == 422


async def test_validation_error_error_field(exc_app: FastAPI) -> None:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=exc_app), base_url="http://test"
    ) as client:
        response = await client.get("/raise/validation-error")

    assert response.json()["error"] == "validation_error"


async def test_validation_error_detail_contains_message(exc_app: FastAPI) -> None:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=exc_app), base_url="http://test"
    ) as client:
        response = await client.get("/raise/validation-error")

    assert "bad input" in response.json()["detail"]
