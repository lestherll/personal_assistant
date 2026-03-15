"""Shared fixtures for all tests (unit, functional, evaluation).

Each test that needs a live server receives a ``live_server_url`` fixture
which starts a real Uvicorn server in a background thread, yields the base
URL, then shuts it down cleanly.  Running the server in a separate thread
means its event loop is always active and can accept requests regardless of
which asyncio event loop the test is currently running.
"""

from __future__ import annotations

import os

# AUTH_DISABLED must be set before api.main is imported because
# api/dependencies.py evaluates it at module level.  DATABASE_URL is set
# inside the live_server_url fixture (only needed before the server starts).
os.environ["AUTH_DISABLED"] = "true"

import socket
import tempfile
import threading
import uuid as _uuid
from collections.abc import AsyncIterator

import httpx
import pytest
import sqlalchemy
import uvicorn
from sqlalchemy.orm import Session

from api.main import app


def _free_port() -> int:
    """Return a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _seed_database(db_file: str) -> None:
    """Create tables and seed the DEV_USER + default workspace synchronously."""
    from personal_assistant.bootstrap import build_registry
    from personal_assistant.core.orchestrator import Orchestrator
    from personal_assistant.persistence.models import Base, User, UserAgent, UserWorkspace
    from personal_assistant.workspaces.default_workspace import create_default_workspace

    sync_url = f"sqlite:///{db_file}"
    engine = sqlalchemy.create_engine(sync_url)
    Base.metadata.create_all(engine)

    dev_user_id = _uuid.UUID(int=0)

    with Session(engine) as session:
        # Skip seeding if already done (e.g. re-used fixture)
        if session.get(User, dev_user_id) is not None:
            engine.dispose()
            return

        # Insert the DEV_USER sentinel so FK constraints are satisfied
        session.add(
            User(
                id=dev_user_id,
                username="dev",
                email="dev@local",
                hashed_password="",
                is_active=True,
            )
        )
        session.flush()

        # Build the default workspace from the template orchestrator and
        # persist it as UserWorkspace/UserAgent rows for the DEV_USER.
        registry = build_registry()
        orchestrator = Orchestrator(registry)
        default_ws = create_default_workspace(orchestrator)

        ws_row = UserWorkspace(
            user_id=dev_user_id,
            name=default_ws.config.name,
            description=default_ws.config.description,
        )
        session.add(ws_row)
        session.flush()

        for agent_name in default_ws.list_agents():
            agent = default_ws.get_agent(agent_name)
            if agent is None:
                continue
            session.add(
                UserAgent(
                    user_workspace_id=ws_row.id,
                    name=agent.config.name,
                    description=agent.config.description,
                    system_prompt=agent.config.system_prompt,
                    provider=agent.config.provider,
                    model=agent.config.model,
                    allowed_tools=list(agent.config.allowed_tools),
                )
            )

        session.commit()

    engine.dispose()


@pytest.fixture(scope="session")
def live_server_url() -> str:
    """Start a Uvicorn server in a background thread and return its base URL.

    Session-scoped so the server is started once and shared across all tests.
    Running in a thread (not a coroutine) means the server's event loop is
    always active — tests that run their own event loops can still reach it.
    """
    # Create a temp SQLite file and seed it before the server starts.
    db_file = tempfile.mktemp(suffix=".db", prefix="test_pa_")
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_file}"
    _seed_database(db_file)

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
