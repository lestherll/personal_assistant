"""Shared fixtures for all tests (unit, functional, evaluation).

Each test that needs a live server receives a ``live_server_url`` fixture
which starts a real Uvicorn server in a background thread, yields the base
URL, then shuts it down cleanly.  Running the server in a separate thread
means its event loop is always active and can accept requests regardless of
which asyncio event loop the test is currently running.

When Docker is available, a real PostgreSQL container (via testcontainers) is
used so the test database matches production.  When Docker is unavailable the
fixture falls back to a temporary SQLite file (via aiosqlite).
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


# ---------------------------------------------------------------------------
# Testcontainers helpers
# ---------------------------------------------------------------------------


def _docker_available() -> bool:
    """Return True if Docker daemon is reachable."""
    import shutil
    import subprocess

    if not shutil.which("docker"):
        return False
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _start_postgres_container() -> tuple[object, str, str] | None:
    """Start a PostgreSQL testcontainer.

    Returns ``(container, async_url, sync_url)`` on success, or ``None`` if
    Docker or testcontainers are not available.
    """
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        return None

    if not _docker_available():
        return None

    try:
        container = PostgresContainer("postgres:16-alpine", driver=None)
        container.start()

        host = container.get_container_host_ip()
        port = container.get_exposed_port(5432)
        user = container.username
        password = container.password
        dbname = container.dbname

        sync_url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{dbname}"
        async_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"

        return container, async_url, sync_url
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Database seeding
# ---------------------------------------------------------------------------


def _seed_database(sync_url: str) -> None:
    """Create tables and seed the DEV_USER + default workspace synchronously."""
    from personal_assistant.bootstrap import build_registry
    from personal_assistant.core.orchestrator import Orchestrator
    from personal_assistant.persistence.models import Base, User, UserAgent, UserWorkspace
    from personal_assistant.workspaces.default_workspace import create_default_workspace

    engine = sqlalchemy.create_engine(sync_url)

    # On PostgreSQL, manually create the message_role enum type before
    # create_all because the ORM model declares create_type=False (the
    # production path relies on Alembic migration 0005 instead).
    if engine.dialect.name == "postgresql":
        from personal_assistant.persistence.models import MessageRole

        enum_values = ", ".join(f"'{v.value}'" for v in MessageRole)
        with engine.connect() as conn:
            conn.execute(
                sqlalchemy.text(
                    f"DO $$ BEGIN "
                    f"CREATE TYPE message_role AS ENUM ({enum_values}); "
                    f"EXCEPTION WHEN duplicate_object THEN NULL; "
                    f"END $$"
                )
            )
            conn.commit()

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
                    allowed_tools=list(agent.config.allowed_tools)
                    if agent.config.allowed_tools is not None
                    else None,
                )
            )

        session.commit()

    engine.dispose()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def live_server_url() -> str:
    """Start a Uvicorn server in a background thread and return its base URL.

    Session-scoped so the server is started once and shared across all tests.
    Running in a thread (not a coroutine) means the server's event loop is
    always active — tests that run their own event loops can still reach it.

    Tries a real PostgreSQL container (via testcontainers) first; falls back
    to a temporary SQLite file when Docker is unavailable.
    """
    container = None
    result = _start_postgres_container()

    if result is not None:
        container, async_url, sync_url = result
        os.environ["DATABASE_URL"] = async_url
        _seed_database(sync_url)
        print(f"\n[test-db] Using PostgreSQL testcontainer: {async_url}")
    else:
        # Fallback: SQLite temp file (original behaviour)
        db_file = tempfile.mktemp(suffix=".db", prefix="test_pa_")
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_file}"
        _seed_database(f"sqlite:///{db_file}")
        print(f"\n[test-db] Using SQLite fallback: {db_file}")

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

    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)

        if container is not None:
            container.stop()


@pytest.fixture
async def http_client(live_server_url: str) -> AsyncIterator[httpx.AsyncClient]:
    """Pre-configured AsyncClient pointed at the live server."""
    async with httpx.AsyncClient(base_url=live_server_url) as client:
        yield client
