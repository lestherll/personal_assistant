# Personal Assistant — CLAUDE.md

## Project Overview

A modular AI personal assistant built on LangChain and LangGraph. The core concept is configurable AI agents that specialise in specific tasks, grouped into workspaces, backed by a pluggable AI provider registry.

## Stack

- **Python 3.13**, managed with **uv**
- **LangChain** + **LangGraph** — agent orchestration (ReAct loop via `create_react_agent`)
- **langchain-anthropic** — Anthropic/Claude provider
- **langchain-ollama** — Ollama local provider
- **python-dotenv** — `.env` loading
- **pydantic v2** — tool input schemas + request/response schemas
- **SQLAlchemy 2 (async)** + **asyncpg** — optional PostgreSQL persistence
- **alembic** — database migrations
- **FastAPI** — REST API layer

### Dev tooling
- **ruff** — linting + formatting (`uv run ruff check .` / `uv run ruff format .`)
- **mypy** — static type checking in strict mode (`uv run mypy . --exclude tests`)
- **pytest** + **pytest-mock** + **pytest-asyncio** — unit + functional tests (`uv run pytest`)
- **httpx** — async HTTP client used in API tests

## Project Structure

```
personal_assistant/
├── core/
│   ├── agent.py          # Agent + AgentConfig — LangGraph ReAct agent with history
│   ├── tool.py           # AssistantTool base class (extends LangChain BaseTool)
│   ├── workspace.py      # Workspace + WorkspaceConfig — groups agents + tools
│   └── orchestrator.py   # Orchestrator — manages registry, workspaces, task routing
├── providers/
│   ├── base.py           # AIProvider + ProviderConfig abstract base
│   ├── registry.py       # ProviderRegistry — named provider lookup + default
│   ├── anthropic.py      # AnthropicProvider (ChatAnthropic)
│   └── ollama.py         # OllamaProvider (ChatOllama, local)
├── agents/
│   └── assistant_agent.py  # AssistantAgent — general-purpose starter agent
├── tools/
│   └── example_tool.py     # EchoTool — template for new tools
├── workspaces/
│   └── default_workspace.py  # Factory: wires default agent + tools into a workspace
├── persistence/
│   ├── database.py       # build_engine / build_session_factory (async SQLAlchemy)
│   ├── models.py         # ORM models: Conversation, Message (PostgreSQL + JSONB)
│   └── repository.py     # ConversationRepository — data-access layer
└── services/
    ├── agent_service.py      # AgentService — CRUD + run/stream/reset helpers
    ├── workspace_service.py  # WorkspaceService — CRUD over orchestrator workspaces
    ├── schemas.py            # Pydantic request models (Create/Update/Chat)
    ├── views.py              # Dataclass response views (AgentView, WorkspaceView, …)
    └── exceptions.py         # NotFoundError, AlreadyExistsError, ServiceValidationError
api/
├── main.py               # FastAPI app — lifespan bootstrap, router registration
├── dependencies.py       # FastAPI dependency injection (orchestrator, session factory)
├── exception_handlers.py # Maps service exceptions to HTTP responses
├── schemas.py            # API-level Pydantic request/response schemas
└── routers/
    ├── agents.py         # /agents/** endpoints
    └── workspaces.py     # /workspaces/** endpoints
tests/
├── unit/
│   ├── conftest.py           # Shared fixtures
│   ├── core/                 # Tests for agent, workspace, orchestrator
│   ├── providers/            # Tests for provider registry
│   ├── services/             # Tests for workspace_service, agent_service
│   └── api/                  # Unit tests for routers, dependencies, exception handlers
└── functional/
    └── api/                  # End-to-end API tests (httpx AsyncClient against live app)
main.py                       # REPL entry point — bootstraps registry, orchestrator
```

## Key Concepts

### Providers
Registered in a `ProviderRegistry` by name. Each provider wraps a LangChain chat model and exposes `get_model(model, **kwargs)`. Add new providers by subclassing `AIProvider`.

### Agents
Created from `AgentConfig` (name, description, system_prompt, provider, model, allowed_tools). Maintain their own conversation history across turns. Rebuilt automatically when tools are added/removed.

### Workspaces
Named containers for agents and tools. Tools added to a workspace are auto-registered with all compatible agents. Supports `add_agent`, `remove_agent`, `replace_agent`, `add_tool`, `remove_tool`.

### Orchestrator
Owns the `ProviderRegistry` and all workspaces. Routes tasks via `delegate(task, agent_name, workspace_name, session=...)`. Helpers: `create_agent(config)`, `replace_agent(config)`, `create_workspace(config)`, `remove_workspace(name)`.

### Services
Thin business-logic layer sitting above the core. `WorkspaceService` and `AgentService` wrap the orchestrator with CRUD operations and raise typed exceptions (`NotFoundError`, `AlreadyExistsError`). Pydantic schemas in `schemas.py` describe request payloads; dataclass views in `views.py` describe responses.

### REST API
FastAPI app in `api/`. Routers for `/workspaces` and `/agents` delegate to `WorkspaceService` / `AgentService`. Dependencies in `api/dependencies.py` inject the orchestrator and optional session factory from `app.state`. Exception handlers in `api/exception_handlers.py` convert service exceptions to appropriate HTTP status codes. Start with `uv run fastapi dev api/main.py`.

### Persistence (optional)
Async SQLAlchemy + asyncpg backed by PostgreSQL. `Conversation` and `Message` ORM models live in `persistence/models.py`. `ConversationRepository` handles all DB access. Set `DATABASE_URL` to enable; omit it to run in-memory only. Use Alembic for migrations.

## Environment

Copy `.env.example` to `.env` and set:
```
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/personal_assistant  # optional
```

Ollama runs locally at `http://localhost:11434`. Pull models with `ollama pull <model>`.

## Commands

```bash
uv run python main.py              # Start the REPL
uv run fastapi dev api/main.py     # Start the REST API (dev mode)
uv add <package>                   # Add a dependency
uv run pytest                      # Run all tests (unit + functional)
uv run ruff check .                # Lint
uv run ruff format .               # Format
uv run mypy . --exclude tests      # Type-check
```

## Conventions

- New tools: subclass `AssistantTool` in `personal_assistant/tools/`, define `name`, `description`, `args_schema` (Pydantic model), and `_run()`.
- New agents: subclass `Agent` or use `AgentConfig` directly with `orchestrator.create_agent()`. Use `AgentService` when calling from service/API layers.
- New providers: subclass `AIProvider` in `personal_assistant/providers/`, implement `get_model()`, register in `main.py`.
- New workspaces: add a factory function in `personal_assistant/workspaces/`. Use `WorkspaceService` when calling from service/API layers.
- New API endpoints: add a router in `api/routers/`, include it in `api/main.py`, and add any new service exceptions to `api/exception_handlers.py`.
- Do not hardcode API keys — always use `.env`.
- Agent conversation history persists per agent instance. Call `agent.reset()` or `AgentService.reset_agent()` to clear.
- `DATABASE_URL` is optional. When absent, the app runs fully in-memory with no persistence.
- Service exceptions (`NotFoundError`, `AlreadyExistsError`) are in `services/exceptions.py` — catch these at API/CLI boundaries.
