# Personal Assistant — CLAUDE.md

## Project Overview

A modular AI personal assistant built on LangChain and LangGraph. The core concept is configurable AI agents that specialise in specific tasks, grouped into workspaces, backed by a pluggable AI provider registry.

## Stack

- **Python 3.13**, managed with **uv**
- **LangChain** + **LangGraph** — agent orchestration (ReAct loop via `create_agent`)
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
├── bootstrap.py          # build_registry() — shared provider registry setup for REPL + API
├── core/
│   ├── agent.py          # Agent + AgentConfig — LangGraph ReAct agent with history
│   ├── tool.py           # AssistantTool base class (extends LangChain BaseTool)
│   ├── workspace.py      # Workspace + WorkspaceConfig — groups agents + tools
│   ├── orchestrator.py   # Orchestrator — manages registry, workspaces, task routing
│   └── supervisor.py     # WorkspaceSupervisor — LangGraph StateGraph routing messages to agents
├── providers/
│   ├── base.py           # AIProvider + ProviderConfig abstract base
│   ├── registry.py       # ProviderRegistry — named provider lookup + default
│   ├── anthropic.py      # AnthropicProvider (ChatAnthropic)
│   └── ollama.py         # OllamaProvider (ChatOllama, local)
├── agents/
│   ├── assistant_agent.py    # AssistantAgent — general-purpose starter agent
│   ├── career_agent.py       # CareerAgent — resume/cover letter/interview prep
│   ├── coding_agent.py       # PythonCodingAgent — Python coding, debugging, code review
│   └── research_agent.py     # GeneralResearchAgent — article summarisation, Q&A
├── tools/
│   ├── example_tool.py     # EchoTool, AgentInformationTool — tool examples/templates
│   └── indeed_tool.py      # IndeedJobSearchTool — job search via RapidAPI/Indeed (needs RAPIDAPI_KEY)
├── workspaces/
│   └── default_workspace.py  # Factory: wires default agents + tools into a workspace
├── persistence/
│   ├── database.py       # build_engine / build_session_factory (async SQLAlchemy)
│   ├── models.py         # ORM models: Conversation, Message (PostgreSQL + JSONB)
│   └── repository.py     # ConversationRepository — data-access layer
└── services/
    ├── agent_service.py          # AgentService — CRUD + run/stream/reset + conversation lifecycle
    ├── workspace_service.py      # WorkspaceService — CRUD over orchestrator workspaces
    ├── conversation_pool.py      # ConversationPool — LRU in-memory pool of per-conversation agent clones
    ├── conversation_service.py   # ConversationService — get/create clones, cold-start from DB
    ├── schemas.py                # Pydantic request models (Create/Update/Chat)
    ├── views.py                  # Dataclass response views (AgentView, WorkspaceView, ConversationView, …)
    └── exceptions.py             # NotFoundError, AlreadyExistsError, ServiceValidationError
api/
├── main.py               # FastAPI app — lifespan bootstrap, router registration
├── dependencies.py       # FastAPI dependency injection (orchestrator, session factory)
├── exception_handlers.py # Maps service exceptions to HTTP responses; catch-all 500 for unexpected errors
├── schemas.py            # API-level Pydantic request/response schemas
└── routers/
    ├── agents.py         # /agents/** endpoints (including conversation list/delete)
    ├── workspaces.py     # /workspaces/** endpoints
    └── params.py         # Reusable annotated Path params (WorkspaceName, AgentName)
tests/
├── unit/
│   ├── conftest.py           # Shared fixtures
│   ├── core/                 # Tests for agent, workspace, orchestrator, supervisor
│   ├── providers/            # Tests for provider registry
│   ├── services/             # Tests for workspace_service, agent_service, conversation_pool, conversation_service
│   ├── tools/                # Tests for individual tools
│   ├── api/                  # Unit tests for routers, dependencies, exception handlers
│   └── test_bootstrap.py     # Tests for build_registry()
├── functional/
│   └── api/                  # End-to-end API tests (httpx AsyncClient against live app)
└── evaluation/
    ├── conftest.py           # DeepEval judge fixture (Ollama-backed)
    └── api/
        ├── test_chat.py            # Evaluation tests for agent chat endpoints
        └── test_workspace_chat.py  # Evaluation tests for workspace chat endpoint
main.py                       # REPL entry point — bootstraps registry, orchestrator
```

## Key Concepts

### Bootstrap
`personal_assistant/bootstrap.py` exports `build_registry() -> ProviderRegistry`, which registers `AnthropicProvider` and `OllamaProvider` (set as default). Both `main.py` (REPL) and `api/main.py` call this function; do not duplicate registration elsewhere.

### Providers
Registered in a `ProviderRegistry` by name. Each provider wraps a LangChain chat model and exposes `get_model(model, **kwargs)`. Add new providers by subclassing `AIProvider`.

### Agents
Created from `AgentConfig` (name, description, system_prompt, provider, model, allowed_tools). Maintain their own conversation history across turns. Rebuilt automatically when tools are added/removed.

### Workspaces
Named containers for agents and tools. Tools added to a workspace are auto-registered with all compatible agents. Supports `add_agent`, `remove_agent`, `replace_agent`, `add_tool`, `remove_tool`. Each workspace owns a `WorkspaceSupervisor` that routes workspace-level chat to the most suitable agent.

- `add_agent` raises `ValueError` if an agent with that name already exists (use `replace_agent` to swap).
- `remove_agent` and `remove_tool` raise `KeyError` if the name is not found.
- Agent-private tools can be registered via `add_tool_to_agent(agent_name, tool)` — they are not shared with other agents and do not appear in `list_tools()`.

### Supervisor
`WorkspaceSupervisor` (`core/supervisor.py`) builds a LangGraph `StateGraph` with a supervisor node and one node per agent. The supervisor LLM picks the target agent; conversation state is persisted across turns via LangGraph's `MemorySaver` checkpointer, keyed by `thread_id`. Call `supervisor.run(message, thread_id)` → `(response, thread_id, agent_used)`. `rebuild(agents)` re-compiles the graph when the agent roster changes.

### ConversationPool
`ConversationPool` (`services/conversation_pool.py`) is an in-memory LRU pool of per-conversation `Agent` clones, keyed by `(workspace_name, agent_name, conversation_id)`. Evicts the least-recently-used entry when `max_size` is reached and supports TTL-based expiry via `evict_expired()`.

### ConversationService
`ConversationService` (`services/conversation_service.py`) manages agent clones for individual conversations. On a pool hit it returns the existing clone; for new conversations it clones the template and optionally persists via the DB; for cold-starts (known `conversation_id`, pool miss) it validates against the DB and rebuilds the clone.

### Orchestrator
Owns the `ProviderRegistry` and all workspaces. Routes tasks via `delegate(task, agent_name, workspace_name, session=...)`. Helpers: `create_agent(config)`, `replace_agent(config)`, `create_workspace(config)`, `remove_workspace(name)`.

### Services
Thin business-logic layer sitting above the core. `WorkspaceService` and `AgentService` wrap the orchestrator with CRUD operations and raise typed exceptions (`NotFoundError`, `AlreadyExistsError`). Pydantic schemas in `schemas.py` describe request payloads; dataclass views in `views.py` describe responses.

`AgentService` also provides conversation lifecycle methods: `list_conversations(workspace, agent, session)` and `delete_conversation(workspace, agent, id, session)`. Both require a DB session and raise `NotFoundError` when the resource is absent.

### REST API
FastAPI app in `api/`. Routers for `/workspaces` and `/agents` delegate to `WorkspaceService` / `AgentService`. Dependencies in `api/dependencies.py` inject the orchestrator and optional session factory from `app.state`. Exception handlers in `api/exception_handlers.py` convert service exceptions to appropriate HTTP status codes; a catch-all `Exception` handler returns `{"error": "internal_server_error"}` with 500 and logs the full traceback. Start with `uv run fastapi dev api/main.py`.

### Persistence (optional)
Async SQLAlchemy + asyncpg backed by PostgreSQL. `Conversation` and `Message` ORM models live in `persistence/models.py`. `ConversationRepository` handles all DB access. Set `DATABASE_URL` to enable; omit it to run in-memory only. Use Alembic for migrations.

### Evaluation (optional)
DeepEval-based evaluation tests for chat endpoints. Located in `tests/evaluation/api/test_chat.py`. Tests use an Ollama-backed judge model (`qwen2.5:14b`) to evaluate LLM responses for relevancy, correctness, and toxicity. Run with `uv run pytest -m evaluation tests/evaluation/` (requires local Ollama running at `http://localhost:11434`). Streaming endpoints use SSE with raw text tokens and `[DONE]` sentinel; non-streaming endpoints use JSON request/response format. Use `timeout=120.0` when making requests to LLM-backed endpoints to avoid timeout errors.

## Environment

Copy `.env.example` to `.env` and set:
```
ANTHROPIC_API_KEY=sk-ant-...
RAPIDAPI_KEY=...                   # optional — enables IndeedJobSearchTool
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/personal_assistant  # optional
```

Ollama runs locally at `http://localhost:11434`. Pull models with `ollama pull <model>`.

## Commands

```bash
uv run python main.py                          # Start the REPL
uv run fastapi dev api/main.py                 # Start the REST API (dev mode)
uv add <package>                               # Add a dependency
uv run pytest                                  # Run unit + functional tests (evaluation skipped by default)
uv run pytest tests/                           # Run unit + functional tests (evaluation skipped by default)
uv run pytest -m evaluation tests/evaluation/  # Run evaluation tests only (requires local Ollama)
uv run ruff check .                            # Lint
uv run ruff format .                           # Format
uv run mypy . --exclude tests                  # Type-check
```

## Conventions

- New tools: subclass `AssistantTool` in `personal_assistant/tools/`, define `name`, `description`, `args_schema` (Pydantic model), and `_run()`. To give a tool access to the calling agent's `AgentConfig`, add an `agent_config: AgentConfig | None = None` field — `Agent.register_tool` detects this via `model_fields` and injects a copy automatically via `model_copy`, so each agent gets its own bound instance and the original tool is never mutated.
- New agents: subclass `Agent` (see `career_agent.py`, `coding_agent.py`, `research_agent.py` for examples) or use `AgentConfig` directly with `orchestrator.create_agent()`. Use `AgentService` when calling from service/API layers.
- New providers: subclass `AIProvider` in `personal_assistant/providers/`, implement `get_model()`, register via `build_registry()` in `personal_assistant/bootstrap.py`.
- New workspaces: add a factory function in `personal_assistant/workspaces/`. Use `WorkspaceService` when calling from service/API layers.
- New API endpoints: add a router in `api/routers/`, include it in `api/main.py`, and add any new service exceptions to `api/exception_handlers.py`. Reuse or extend annotated path parameters from `api/routers/params.py`.
- Do not hardcode API keys — always use `.env`.
- Agent conversation history persists per agent instance. Call `agent.reset()` or `AgentService.reset_agent()` to clear.
- `DATABASE_URL` is optional. When absent, the app runs fully in-memory with no persistence. Conversation list/delete endpoints return empty lists / 404 when no DB is configured.
- Service exceptions (`NotFoundError`, `AlreadyExistsError`, `ServiceValidationError`) are in `services/exceptions.py` — catch these at API/CLI boundaries.
