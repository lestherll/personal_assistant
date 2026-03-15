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
├── auth/
│   ├── __init__.py       # package marker
│   ├── password.py       # hash_password / verify_password (pwdlib + Argon2)
│   └── tokens.py         # create_access_token / create_refresh_token / decode_token (PyJWT HS256)
├── persistence/
│   ├── database.py       # build_engine / build_session_factory (async SQLAlchemy)
│   ├── models.py         # ORM models: User, UserWorkspace, UserAgent, Conversation, Message
│   ├── repository.py     # ConversationRepository — data-access layer
│   ├── user_repository.py            # UserRepository — CRUD for User records
│   └── user_workspace_repository.py  # UserWorkspaceRepository — CRUD + upsert for UserWorkspace/UserAgent
└── services/
    ├── agent_service.py                # AgentService — CRUD + run/stream/reset + conversation lifecycle
    ├── workspace_service.py            # WorkspaceService — CRUD over orchestrator workspaces
    ├── auth_service.py                 # AuthService — register/login/refresh/get_user_from_token
    ├── conversation_pool.py            # ConversationPool — LRU pool keyed by (user_id, workspace, agent, conv_id)
    ├── conversation_service.py         # ConversationService — get/create clones, cold-start from DB
    ├── user_orchestrator_registry.py   # UserOrchestratorRegistry — per-user Orchestrator cache
    ├── schemas.py                      # Pydantic request models (Create/Update/Chat)
    ├── views.py                        # Dataclass response views (AgentView, WorkspaceView, ConversationView, …)
    └── exceptions.py                   # NotFoundError, AlreadyExistsError, ServiceValidationError, AuthError, ForbiddenError
api/
├── main.py               # FastAPI app — lifespan bootstrap, router registration
├── dependencies.py       # FastAPI dependency injection (orchestrator, auth, session factory)
├── exception_handlers.py # Maps service exceptions to HTTP responses; catch-all 500 for unexpected errors
├── schemas.py            # API-level Pydantic request/response schemas (including auth schemas)
└── routers/
    ├── auth.py           # /auth/** endpoints (register, login, refresh)
    ├── agents.py         # /agents/** endpoints (including conversation list/delete)
    ├── workspaces.py     # /workspaces/** endpoints (chat + streaming)
    ├── providers.py      # /providers/** endpoints (discovery)
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
Registered in a `ProviderRegistry` by name. Each provider wraps a LangChain chat model and exposes `get_model(model, **kwargs)` and `async list_models() -> list[str]`. The default `list_models()` implementation returns `[default_model]`; concrete providers override it to return the full set of supported models (`AnthropicProvider` returns a hardcoded list; `OllamaProvider` queries the local `/api/tags` endpoint and falls back to `[default_model]` on error). Add new providers by subclassing `AIProvider`.

### Agents
Created from `AgentConfig` (name, description, system_prompt, provider, model, allowed_tools). Maintain their own conversation history across turns. Rebuilt automatically when tools are added/removed.

### Workspaces
Named containers for agents and tools. Tools added to a workspace are auto-registered with all compatible agents. Supports `add_agent`, `remove_agent`, `replace_agent`, `add_tool`, `remove_tool`. Each workspace owns a `WorkspaceSupervisor` that routes workspace-level chat to the most suitable agent.

- `add_agent` raises `ValueError` if an agent with that name already exists (use `replace_agent` to swap).
- `remove_agent` and `remove_tool` raise `KeyError` if the name is not found.
- Agent-private tools can be registered via `add_tool_to_agent(agent_name, tool)` — they are not shared with other agents and do not appear in `list_tools()`.

### Supervisor
`WorkspaceSupervisor` (`core/supervisor.py`) builds a LangGraph `StateGraph` with a supervisor node and one node per agent. The supervisor LLM picks the target agent; conversation state is persisted across turns via LangGraph's `MemorySaver` checkpointer, keyed by `thread_id` (an internal string key). Call `supervisor.run(message, thread_id)` → `(response, thread_id, agent_used)`. `rebuild(agents)` re-compiles the graph when the agent roster changes. At the API level the `thread_id` is exposed as `conversation_id`.

### Authentication
Stateless JWT auth built on `pwdlib` (Argon2 hashing) and `PyJWT` (HS256 tokens).

- `auth/password.py` — `hash_password` / `verify_password`
- `auth/tokens.py` — `create_access_token(sub)`, `create_refresh_token(sub)`, `decode_token(token)`. Raises `AuthError` on expired/invalid tokens.
- `services/auth_service.py` — `AuthService`: `register`, `login`, `refresh`, `get_user_from_token`. `fork_default_workspace` is a helper called during registration to copy the global default workspace into the new user's DB rows.
- `api/dependencies.py` — `get_current_user` resolves the `User` from the `Authorization: Bearer` token. When `AUTH_DISABLED=true`, it returns a fixed `DEV_USER` sentinel without touching the DB. `CurrentUserDep = Annotated[User, Depends(get_current_user)]` is imported by all routers.
- **Dev bypass:** Set `AUTH_DISABLED=true` in `.env` to skip all auth. `DATABASE_URL` is then optional and the app runs fully in-memory as the `dev` user.
- **DB required:** When `AUTH_DISABLED=false` (default), the app will refuse to start without `DATABASE_URL`.

### Per-User Orchestrator Registry
`UserOrchestratorRegistry` (`services/user_orchestrator_registry.py`) caches a personal `Orchestrator` per user ID. The global template Orchestrator (on `app.state.orchestrator`) is **never mutated** by user requests — it only serves as the provider-registry source.

`get_user_orchestrator` (in `api/dependencies.py`) checks the registry cache first, then loads the user's `UserWorkspace`/`UserAgent` DB rows and calls `build_and_cache` on a miss. In dev/no-DB mode it falls back to the template orchestrator.

### ConversationPool
`ConversationPool` (`services/conversation_pool.py`) is an in-memory LRU pool of per-conversation `Agent` clones, keyed by `(user_id | None, workspace_name, agent_name, conversation_id)`. Evicts the least-recently-used entry when `max_size` is reached and supports TTL-based expiry via `evict_expired()`.

### ConversationService
`ConversationService` (`services/conversation_service.py`) manages agent clones for individual conversations. On a pool hit it returns the existing clone; for new conversations it clones the template and optionally persists via the DB; for cold-starts (known `conversation_id`, pool miss) it validates against the DB and rebuilds the clone.

`get_or_create_clone()` accepts optional `llm_override: BaseChatModel | None` and `user_id: UUID | None` keyword arguments. `llm_override` clones ephemerally (not pooled). `user_id` scopes the pool key and is stored on the `Conversation` DB row for ownership filtering.

### Orchestrator
Owns the `ProviderRegistry` and all workspaces. Routes tasks via `delegate(task, agent_name, workspace_name, session=...)`. Helpers: `create_agent(config)`, `replace_agent(config)`, `create_workspace(config)`, `remove_workspace(name)`.

### Services
Thin business-logic layer sitting above the core. `WorkspaceService` and `AgentService` wrap the orchestrator with CRUD operations and raise typed exceptions (`NotFoundError`, `AlreadyExistsError`). Pydantic schemas in `schemas.py` describe request payloads; dataclass views in `views.py` describe responses.

`AgentService` also provides conversation lifecycle methods: `list_conversations(workspace, agent, session)` and `delete_conversation(workspace, agent, id, session)`. Both require a DB session and raise `NotFoundError` when the resource is absent.

### REST API
FastAPI app in `api/`. Routers for `/workspaces`, `/agents`, and `/providers` delegate to `WorkspaceService` / `AgentService` / `ProviderRegistry`. Dependencies in `api/dependencies.py` inject the orchestrator, `ConversationService`, and optional session factory from `app.state`. Exception handlers in `api/exception_handlers.py` convert service exceptions to appropriate HTTP status codes; a catch-all `Exception` handler returns `{"error": "internal_server_error"}` with 500 and logs the full traceback. Start with `uv run fastapi dev api/main.py`.

**Authentication endpoints** (`/auth/register`, `/auth/login`, `/auth/refresh`) — open (no token required). All other endpoints require `Authorization: Bearer <token>`.

**Workspace chat** (`POST /workspaces/{name}/chat`) supports two routing modes controlled by the `WorkspaceChatRequest` body:
- **Supervisor path** (default): omit `agent_name`; the supervisor LLM picks the best agent. Uses `conversation_id` to thread turns.
- **Agent-direct path**: set `agent_name` to skip the supervisor. Optionally set `provider` and/or `model` to override the LLM for this turn only (ephemeral — not pooled). Returns `conversation_id` that can be passed back on subsequent turns.

**Workspace streaming** (`POST /workspaces/{name}/chat/stream`) requires `agent_name` (supervisor streaming is not supported). Returns `text/event-stream` with `data: {token}\n\n` lines and a `data: [DONE]\n\n` sentinel. `X-Conversation-Id` and `X-Agent-Used` response headers carry the conversation metadata.

**Provider discovery** (`GET /providers/`, `GET /providers/{name}/models`) lists registered providers and their available models.

### Persistence
Async SQLAlchemy + asyncpg backed by PostgreSQL. ORM models live in `persistence/models.py`: `User`, `UserWorkspace`, `UserAgent`, `Conversation`, `Message`. Set `DATABASE_URL` to enable; omit it only when `AUTH_DISABLED=true` (in-memory dev mode). Use Alembic for migrations (`uv run alembic upgrade head`).

### Evaluation (optional)
DeepEval-based evaluation tests for chat endpoints. Located in `tests/evaluation/api/test_chat.py`. Tests use an Ollama-backed judge model (`qwen2.5:14b`) to evaluate LLM responses for relevancy, correctness, and toxicity. Run with `uv run pytest -m evaluation tests/evaluation/` (requires local Ollama running at `http://localhost:11434`). Streaming endpoints use SSE with raw text tokens and `[DONE]` sentinel; non-streaming endpoints use JSON request/response format. Use `timeout=120.0` when making requests to LLM-backed endpoints to avoid timeout errors.

## Environment

Copy `.env.example` to `.env` and set:
```
ANTHROPIC_API_KEY=sk-ant-...
RAPIDAPI_KEY=...                   # optional — enables IndeedJobSearchTool
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/personal_assistant
SECRET_KEY=<random-32-bytes>       # generate with: openssl rand -hex 32
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
AUTH_DISABLED=false                # set true to skip auth (dev/test only, allows no DATABASE_URL)
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
- Service exceptions (`NotFoundError`, `AlreadyExistsError`, `ServiceValidationError`, `AuthError`, `ForbiddenError`) are in `services/exceptions.py` — catch these at API/CLI boundaries. `AuthError` maps to HTTP 401; `ForbiddenError` to 403.
- New auth flows: use `AuthService` (not raw token functions) from the service layer. `fork_default_workspace` is called automatically on registration — do not call it manually.
- Password hashing uses `pwdlib` with Argon2 (`auth/password.py`). JWT tokens use `PyJWT` with HS256 (`auth/tokens.py`). Do not use `passlib` or `python-jose`.
- All workspace/agent routes require `CurrentUserDep`. The dep resolves the per-user `Orchestrator` via `UserOrchestratorRegistry` so each user sees only their own workspaces and agents.
