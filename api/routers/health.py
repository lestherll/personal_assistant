"""Health check router."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

router = APIRouter(tags=["health"])


class ComponentStatus(BaseModel):
    status: str  # "ok" | "unavailable" | "error"
    latency_ms: float | None = None


class HealthResponse(BaseModel):
    status: str  # "ok" | "degraded" | "unhealthy"
    latency_ms: float
    components: dict[str, ComponentStatus]


async def _check_database(
    session_factory: async_sessionmaker[AsyncSession] | None,
) -> ComponentStatus:
    if session_factory is None:
        return ComponentStatus(status="unavailable")
    start = time.monotonic()
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        latency_ms = (time.monotonic() - start) * 1000
        return ComponentStatus(status="ok", latency_ms=latency_ms)
    except Exception:
        return ComponentStatus(status="error")


def _derive_status(components: dict[str, ComponentStatus]) -> str:
    statuses = {c.status for c in components.values()}
    if "error" in statuses:
        return "unhealthy"
    if "unavailable" in statuses:
        return "degraded"
    return "ok"


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    start = time.monotonic()
    session_factory: async_sessionmaker[AsyncSession] | None = request.app.state.session_factory
    db_status = await _check_database(session_factory)
    components: dict[str, ComponentStatus] = {"database": db_status}
    overall = _derive_status(components)
    latency_ms = (time.monotonic() - start) * 1000
    return HealthResponse(status=overall, latency_ms=latency_ms, components=components)
