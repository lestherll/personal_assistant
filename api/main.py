from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langchain_core.tools import BaseTool

from api.exception_handlers import register_exception_handlers
from api.routers import agents, auth, health, providers, workspaces
from personal_assistant.bootstrap import build_registry
from personal_assistant.config import get_settings
from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.persistence.database import build_engine, build_session_factory
from personal_assistant.services.agent_service import AgentService
from personal_assistant.services.conversation_cache import InMemoryConversationCache
from personal_assistant.services.workspace_service import WorkspaceService
from personal_assistant.tools.example_tool import AgentInformationTool, EchoTool
from personal_assistant.tools.indeed_tool import IndeedJobSearchTool
from personal_assistant.workspaces.default_workspace import create_default_workspace


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # --- Auth check ---
    settings = get_settings()
    if not settings.database_url and not settings.auth_disabled:
        raise RuntimeError(
            "DATABASE_URL is required when AUTH_DISABLED is not set to 'true'. "
            "Set AUTH_DISABLED=true to run in-memory dev mode."
        )

    # --- Provider registry ---
    registry = build_registry()

    # --- Template orchestrator (for dev/REPL fallback) ---
    orchestrator = Orchestrator(registry)
    create_default_workspace(orchestrator)
    app.state.orchestrator = orchestrator

    # --- Tools available to all agents ---
    tools: list[BaseTool] = [EchoTool(), AgentInformationTool(), IndeedJobSearchTool()]
    app.state.tools = tools

    # --- Singleton services ---
    cache = InMemoryConversationCache(max_size=1000)
    agent_service = AgentService(registry, tools, cache)
    workspace_service = WorkspaceService(registry, agent_service)
    app.state.agent_service = agent_service
    app.state.workspace_service = workspace_service

    # --- Persistence (optional) ---
    engine = None
    if settings.database_url:
        engine = build_engine(settings.database_url)
        app.state.session_factory = build_session_factory(engine)
    else:
        app.state.session_factory = None

    yield

    if engine is not None:
        await engine.dispose()


app = FastAPI(title="Personal Assistant API", version="0.1.0", lifespan=lifespan)
register_exception_handlers(app)
app.include_router(auth.router)
app.include_router(workspaces.router)
app.include_router(agents.router)
app.include_router(providers.router)
app.include_router(health.router)
