"""Shared fixtures for functional tests.

Each test that needs a live server receives a ``live_server_url`` fixture
which starts a real Uvicorn process bound to a random port, yields the base
URL, then shuts it down cleanly.
"""

from __future__ import annotations

import asyncio
import socket
from collections.abc import AsyncIterator

import httpx
import pytest
import uvicorn

from api.main import app


def _free_port() -> int:
    """Return a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
async def live_server_url() -> AsyncIterator[str]:
    """Start a real Uvicorn server and yield its base URL."""
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, lifespan="on", log_level="warning")
    server = uvicorn.Server(config)

    serve_task = asyncio.create_task(server.serve())

    # Wait until uvicorn signals it has finished startup.
    while not server.started:
        await asyncio.sleep(0.05)

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    await serve_task


@pytest.fixture
async def http_client(live_server_url: str) -> AsyncIterator[httpx.AsyncClient]:
    """Pre-configured AsyncClient pointed at the live server."""
    async with httpx.AsyncClient(base_url=live_server_url) as client:
        yield client
