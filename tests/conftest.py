"""Shared fixtures for all tests (unit, functional, evaluation).

Each test that needs a live server receives a ``live_server_url`` fixture
which starts a real Uvicorn server in a background thread, yields the base
URL, then shuts it down cleanly.  Running the server in a separate thread
means its event loop is always active and can accept requests regardless of
which asyncio event loop the test is currently running.
"""

from __future__ import annotations

import os

# deepeval's pytest plugin loads .env at import time (before conftest runs), which can set
# AUTH_DISABLED=false from the project's .env file.  When no DATABASE_URL is configured
# the app requires AUTH_DISABLED=true to start, so we enforce it here for tests.
if not os.environ.get("DATABASE_URL"):
    os.environ["AUTH_DISABLED"] = "true"

import socket
import threading
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


@pytest.fixture(scope="session")
def live_server_url() -> str:
    """Start a Uvicorn server in a background thread and return its base URL.

    Session-scoped so the server is started once and shared across all tests.
    Running in a thread (not a coroutine) means the server's event loop is
    always active — tests that run their own event loops can still reach it.
    """
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, lifespan="on", log_level="warning")
    server = uvicorn.Server(config)

    started = threading.Event()
    original_startup = server.startup

    async def _patched_startup(sockets: object = None) -> None:
        await original_startup(sockets=sockets)
        started.set()

    server.startup = _patched_startup

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    started.wait(timeout=10)

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture
async def http_client(live_server_url: str) -> AsyncIterator[httpx.AsyncClient]:
    """Pre-configured AsyncClient pointed at the live server."""
    async with httpx.AsyncClient(base_url=live_server_url) as client:
        yield client
