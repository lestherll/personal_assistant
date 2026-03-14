from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.exception_handlers import register_exception_handlers
from api.routers import agents, providers, workspaces
from personal_assistant.bootstrap import build_registry
from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.persistence.database import build_engine, build_session_factory
from personal_assistant.services.conversation_pool import ConversationPool
from personal_assistant.workspaces.default_workspace import create_default_workspace


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # --- Provider registry ---
    registry = build_registry()

    # --- Orchestrator + default workspace ---
    orchestrator = Orchestrator(registry)
    create_default_workspace(orchestrator)
    app.state.orchestrator = orchestrator

    # --- Conversation pool ---
    pool = ConversationPool(max_size=1000, ttl_seconds=7200.0)
    app.state.conversation_pool = pool

    async def _sweep() -> None:
        while True:
            await asyncio.sleep(900)  # 15 min
            pool.evict_expired()

    sweep_task = asyncio.create_task(_sweep())

    # --- Persistence (optional) ---
    engine = None
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        engine = build_engine(database_url)
        app.state.session_factory = build_session_factory(engine)
    else:
        app.state.session_factory = None

    yield

    sweep_task.cancel()

    if engine is not None:
        await engine.dispose()


app = FastAPI(title="Personal Assistant API", version="0.1.0", lifespan=lifespan)
register_exception_handlers(app)
app.include_router(workspaces.router)
app.include_router(agents.router)
app.include_router(providers.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
