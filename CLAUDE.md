# Personal Assistant — CLAUDE.md

## Project Overview

A modular AI personal assistant built on LangChain and LangGraph. The core concept is configurable AI agents that specialise in specific tasks, grouped into workspaces, backed by a pluggable AI provider registry.

## Stack

- **Python 3.13**, managed with **uv**
- **LangChain** + **LangGraph** — agent orchestration (ReAct loop via `create_agent`)
- **langchain-anthropic** — Anthropic/Claude provider
- **langchain-ollama** — Ollama local provider
- **pydantic v2** — tool input schemas, request/response schemas, and centralised settings (`pydantic-settings`)
- **pydantic-settings** — `.env` loading + typed `Settings` class (`personal_assistant/config.py`)
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
├── config.py             # Settings (pydantic-settings) + get_settings() — centralised env/config
├── bootstrap.py          # build_registry() — shared provider registry setup for REPL + API
├── core/
│   ├── agent.py          # Agent + AgentConfig — LangGraph ReAct agent with history
│   ├── tool.py           # AssistantTool[R] generic base class (extends LangChain BaseTool)
│   ├── workspace.py      # Workspace + WorkspaceConfig — groups agents + tools
│   ├── orchestrator.py   # Orchestrator — manages registry, workspaces, task routing
│   └── supervisor.py     # WorkspaceSupervisor + route() — LangGraph routing + lightweight LLM dispatch
├── providers/
│   ├── base.py           # AIProvider + ProviderConfig abstract base
│   ├── registry.py       # ProviderRegistry — named provider lookup + default
│   ├── anthropic.py      # AnthropicProvider (ChatAnthropic)
│   └── ollama.py         # OllamaProvider (ChatOllama, local, default model: qwen2.5:14b)
├── agents/
│   ├── __init__.py           # DEFAULT_AGENTS dict — lazy factory callables keyed by name
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
│   ├── api_keys.py       # generate_api_key / hash_api_key / verify_api_key (SHA-256)
│   ├── password.py       # hash_password / verify_password (pwdlib + Argon2)
│   └── tokens.py         # create_access_token / create_refresh_token / decode_token (PyJWT HS256)
├── persistence/
│   ├── database.py       # build_engine / build_session_factory (async SQLAlchemy)
│   ├── models.py         # ORM models: User, UserWorkspace, UserAgent, UserAPIKey, Conversation, Message
│   ├── repository.py     # ConversationRepository — data-access layer
│   ├── api_key_repository.py         # APIKeyRepository — CRUD for UserAPIKey records
│   ├── user_repository.py            # UserRepository — CRUD for User records
│   └── user_workspace_repository.py  # UserWorkspaceRepository — CRUD + upsert for UserWorkspace/UserAgent
└── services/
    ├── agent_service.py                # AgentService — DB-first stateless CRUD + run/stream + conversation lifecycle
    ├── workspace_service.py            # WorkspaceService — DB-first stateless CRUD + supervisor routing
    ├── auth_service.py                 # AuthService — register/login/refresh/get_user_from_token
    ├── conversation_cache.py           # ConversationCache ABC + InMemoryConversationCache (LRU)
    ├── schemas.py                      # Pydantic request models (Create/Update/Chat)
    ├── views.py                        # Dataclass response views (AgentView, WorkspaceView, ConversationView, …)
    └── exceptions.py                   # NotFoundError, AlreadyExistsError, ServiceValidationError, AuthError, ForbiddenError
api/
├── main.py               # FastAPI app — lifespan bootstrap, singleton services, router registration
├── dependencies.py       # FastAPI dependency injection (auth, session factory, service singletons, rate limiting)
├── exception_handlers.py # Maps service exceptions to HTTP responses; catch-all 500 for unexpected errors
├── schemas.py            # API-level Pydantic request/response schemas (including auth + API key schemas)
├── streaming.py          # sse_event_generator() — shared SSE wrapper with [DONE]/[ERROR] sentinels
├── rate_limit.py         # RateLimiter — fixed-window per-user rate limiting
└── routers/
    ├── auth.py           # /auth/** endpoints (register, login, refresh, API key CRUD)
    ├── agents.py         # /agents/** endpoints (including conversation list/delete)
    ├── workspaces.py     # /workspaces/** endpoints (chat, streaming, conversations, messages)
    ├── providers.py      # /providers/** endpoints (discovery + health check)
    ├── health.py         # GET /health — liveness probe
    └── params.py         # Reusable annotated Path params (WorkspaceName, AgentName)
tests/
├── unit/
│   ├── conftest.py           # Shared fixtures
│   ├── core/                 # Tests for agent, workspace, orchestrator, supervisor
│   ├── providers/            # Tests for provider registry
│   ├── services/             # Tests for workspace_service, agent_service, conversation_cache, auth_service
│   ├── tools/                # Tests for individual tools
│   ├── api/                  # Unit tests for routers, dependencies, exception handlers
│   ├── persistence/          # Tests for database, models, repositories
│   ├── workspaces/           # Tests for default_workspace factory
│   └── test_bootstrap.py     # Tests for build_registry()
├── functional/
│   └── api/                  # End-to-end API tests (httpx AsyncClient against live app)
└── evaluation/
    ├── conftest.py           # DeepEval judge fixture (Ollama-backed)
    └── api/
        ├── test_chat.py            # Evaluation tests for agent chat endpoints
        └── test_workspace_chat.py  # Evaluation tests for workspace chat endpoint
main.py                       # REPL entry point — bootstraps registry, orchestrator
Dockerfile                    # Python 3.13-slim + uv, uvicorn entrypoint, healthcheck
docker-compose.yml            # app + postgres + alembic migrate services
```

## Key Concepts

### Settings
`personal_assistant/config.py` defines a `Settings` class (extends `pydantic_settings.BaseSettings`) that reads all configuration from environment variables and `.env` files. `get_settings()` returns a module-cached singleton via `@lru_cache`. All code that needs env vars should call `get_settings()` rather than `os.getenv` directly. In tests, patch `get_settings` at the consumer's import path (e.g. `personal_assistant.providers.anthropic.get_settings`).

### Bootstrap
`personal_assistant/bootstrap.py` exports `build_registry() -> ProviderRegistry`, which registers `AnthropicProvider` and `OllamaProvider` (set as default, model `qwen2.5:14b`). Both `main.py` (REPL) and `api/main.py` call this function — do not duplicate registration elsewhere.

### Providers
Registered in a `ProviderRegistry` by name. Each provider wraps a LangChain chat model and exposes `get_model(model, **kwargs)`, `async list_models() -> list[str]`, and `async health() -> dict[str, str]`. The default `list_models()` implementation returns `[default_model]`; concrete providers override it to return the full set of supported models (`AnthropicProvider` returns a hardcoded list; `OllamaProvider` queries the local `/api/tags` endpoint and falls back to `[default_model]` on error). The default `health()` returns `{"status": "ok"}`; `OllamaProvider` overrides it to check `/api/tags` reachability. Add new providers by subclassing `AIProvider`.

### Agents
Created from `AgentConfig` (name, description, system_prompt, provider, model, allowed_tools). Maintain their own conversation history across turns. Rebuilt automatically when tools are added/removed.

`agents/__init__.py` exports `DEFAULT_AGENTS: dict[str, Callable[[ProviderRegistry], Agent]]` — a lazy factory dict of the four built-in agents. Agents are not instantiated until requested.

`AgentConfig` fields:

| Field | Type | Meaning |
|---|---|---|
| `name` | `str` | Identity key across all tiers |
| `description` | `str` | Purpose summary — also used by the supervisor for routing |
| `system_prompt` | `str` | LLM system message |
| `provider` | `str \| None` | Registry key; `None` → registry default |
| `model` | `str \| None` | Model name; `None` → provider default |
| `allowed_tools` | `list[str] \| None` | `None` = all tools, `[]` = no tools, explicit list = allowlist |

### Workspaces
Named containers for agents and tools. Tools added to a workspace are auto-registered with all compatible agents. Supports `add_agent`, `remove_agent`, `replace_agent`, `add_tool`, `remove_tool`. Each workspace owns a `WorkspaceSupervisor` that routes workspace-level chat to the most suitable agent.

- `add_agent` raises `ValueError` if an agent with that name already exists (use `replace_agent` to swap).
- `remove_agent` and `remove_tool` raise `KeyError` if the name is not found.
- Agent-private tools can be registered via `add_tool_to_agent(agent_name, tool)` — they are not shared with other agents and do not appear in `list_tools()`.

### Supervisor
`core/supervisor.py` provides two complementary facilities:

1. **`route(message, agents, llm) -> str`** — lightweight single-shot structured LLM call that returns the name of the best agent for a given message. Used by `WorkspaceService` when routing API requests.
2. **`WorkspaceSupervisor`** — full LangGraph `StateGraph` with a supervisor node and one node per agent, backed by `MemorySaver`. Call `supervisor.run(message, thread_id)` → `(response, thread_id, agent_used)`. `rebuild(agents)` re-compiles the graph when the agent roster changes. Used in the REPL / core layer; at the API level the `thread_id` is exposed as `conversation_id`.

Falls back to the first available agent if the LLM's routing decision is invalid.

### Authentication
Stateless JWT auth built on `pwdlib` (Argon2 hashing) and `PyJWT` (HS256 tokens), with optional API key authentication.

- `auth/password.py` — `hash_password` / `verify_password`
- `auth/tokens.py` — `create_access_token(sub)`, `create_refresh_token(sub)`, `decode_token(token)`. Raises `AuthError` on expired/invalid tokens.
- `auth/api_keys.py` — `generate_api_key()`, `hash_api_key(key)`, `verify_api_key(key, hash)`. Uses SHA-256 (not Argon2) for high-entropy API keys, with `hmac.compare_digest` for timing-safe comparison.
- `services/auth_service.py` — `AuthService`: `register`, `login`, `refresh`, `get_user_from_token`. `fork_default_workspace` is a helper called during registration to copy the global default workspace into the new user's DB rows.
- `api/dependencies.py` — `get_current_user` resolves the `User` from the `Authorization: Bearer` token. Tokens starting with `sk-` are treated as API keys (hashed and looked up in DB); all others go through the JWT path. When `AUTH_DISABLED=true`, it returns a fixed `DEV_USER` sentinel (id=`UUID(int=0)`, username=`"dev"`) without touching the DB. `CurrentUserDep = Annotated[User, Depends(get_current_user)]` is imported by all routers.
- **API keys:** Created via `POST /auth/api-keys`, listed via `GET /auth/api-keys`, revoked via `DELETE /auth/api-keys/{id}`. Keys are stored as SHA-256 hashes in the `user_api_keys` table. The raw key is shown once on creation and never stored.
- **Dev bypass:** Set `AUTH_DISABLED=true` in `.env` to skip all auth. `DATABASE_URL` is then optional and the app runs fully in-memory as the `dev` user.
- **DB required:** When `AUTH_DISABLED=false` (default), the app will refuse to start without `DATABASE_URL`.

### Rate Limiting
Per-user rate limiting is enforced on all chat endpoints via a `rate_limit_chat` FastAPI dependency. Uses a fixed-window algorithm with an in-memory dict (`api/rate_limit.py`). Default: 60 requests per 60 seconds. Returns HTTP 429 with `Retry-After` header when exceeded. The `RateLimiter` singleton is created in the app lifespan and stored on `app.state`.

### SSE Streaming
`api/streaming.py` provides `sse_event_generator(token_iter)` — a shared async generator that wraps any token iterator with SSE formatting (`data: {token}\n\n`), emits `data: [DONE]\n\n` on clean completion, and emits `data: [ERROR]\n\n` on exception. Used by both agent and workspace streaming endpoints.

### ConversationCache
`ConversationCache` (`services/conversation_cache.py`) is an abstract pluggable caching layer for conversation message histories, keyed by `(user_id, workspace_name, conversation_id)`. Methods: `get`, `set`, `invalidate`.

`InMemoryConversationCache` is the built-in LRU implementation backed by `collections.OrderedDict`. The API layer instantiates it as a singleton (`max_size=1000`) at startup. Set `max_size=0` for an unbounded cache.

Future backends can be added by subclassing `ConversationCache` (e.g. `RedisConversationCache`).

### Services

**`AgentService`** (`services/agent_service.py`) — DB-first, stateless singleton.

- Constructor: `AgentService(registry, tools, cache)` where `tools` is the global list of available tools and `cache` is a `ConversationCache` instance.
- Provides CRUD over `UserAgent` DB rows: `create_agent`, `list_agents`, `get_agent`, `update_agent`, `delete_agent`.
- Chat methods: `run_agent(user_id, workspace_name, agent_name, message, *, conversation_id, session)` and `stream_agent(...)`. Both build an ephemeral `Agent` instance per request by loading config from the DB, restore conversation history from cache (or DB on a miss), run the agent, then write the updated history back to the cache.
- Conversation lifecycle: `list_conversations(user_id, workspace_name, session)` and `delete_conversation(user_id, workspace_name, conversation_id, session)`. Both require a DB session.

**`WorkspaceService`** (`services/workspace_service.py`) — DB-first, stateless singleton.

- Constructor: `WorkspaceService(registry, agent_service)`.
- Provides CRUD over `UserWorkspace` DB rows: `create_workspace`, `list_workspaces`, `get_workspace`, `update_workspace`, `delete_workspace`.
- Chat: `chat(...)` and `stream_chat(...)`. When `agent_name` is provided, delegates directly to `AgentService`. Without `agent_name`, loads the workspace's agents from the DB and calls `route()` (lightweight LLM call) to select the best agent, then delegates.

Pydantic schemas in `services/schemas.py` describe request payloads; frozen dataclass views in `services/views.py` describe responses.

### REST API
FastAPI app in `api/`. Singleton `AgentService` and `WorkspaceService` are created once in the `lifespan` hook and stored on `app.state`. Routers retrieve them via `get_agent_service` / `get_workspace_service` DI functions. Exception handlers in `api/exception_handlers.py` convert service exceptions to HTTP status codes; a catch-all `Exception` handler returns `{"error": "internal_server_error"}` with 500 and logs the full traceback. Start with `uv run fastapi dev api/main.py`.

**Authentication endpoints** (`/auth/register`, `/auth/login`, `/auth/refresh`) — open (no token required). All other endpoints require `Authorization: Bearer <token>`.

**Health** (`GET /health`) — liveness probe, always returns 200.

**Workspace chat** (`POST /workspaces/{name}/chat`) supports two routing modes controlled by the `WorkspaceChatRequest` body:
- **Supervisor path** (default): omit `agent_name`; the supervisor LLM picks the best agent via `route()`. Uses `conversation_id` to thread turns.
- **Agent-direct path**: set `agent_name` to skip the supervisor. Optionally set `provider` and/or `model` to override the LLM for this turn only (ephemeral — not persisted). Returns `conversation_id` that can be passed back on subsequent turns.

**Workspace streaming** (`POST /workspaces/{name}/chat/stream`) requires `agent_name` (supervisor streaming is not supported). Returns `text/event-stream` with `data: {token}\n\n` lines and a `data: [DONE]\n\n` sentinel. `X-Conversation-Id` and `X-Agent-Used` response headers carry conversation metadata.

**Provider discovery** (`GET /providers/`, `GET /providers/{name}/models`) lists registered providers and their available models.

### Endpoint Reference

| Method | Path | Description | Auth |
|---|---|---|---|
| `GET` | `/health` | Liveness probe | No |
| `POST` | `/auth/register` | Register a new user | No |
| `POST` | `/auth/login` | Log in, receive access + refresh tokens | No |
| `POST` | `/auth/refresh` | Refresh access token | No |
| `POST` | `/auth/api-keys` | Create an API key | Yes |
| `GET` | `/auth/api-keys` | List API keys for the current user | Yes |
| `DELETE` | `/auth/api-keys/{id}` | Revoke an API key | Yes |
| `GET` | `/providers/` | List all registered providers | Yes |
| `GET` | `/providers/{name}/models` | List available models for a provider | Yes |
| `GET` | `/providers/{name}/health` | Provider health check | Yes |
| `POST` | `/workspaces/` | Create a workspace | Yes |
| `GET` | `/workspaces/` | List workspaces for the current user | Yes |
| `GET` | `/workspaces/{workspace_name}` | Get workspace details | Yes |
| `PATCH` | `/workspaces/{workspace_name}` | Update workspace metadata | Yes |
| `DELETE` | `/workspaces/{workspace_name}` | Delete a workspace | Yes |
| `POST` | `/workspaces/{workspace_name}/chat` | Workspace chat — supervisor or agent-direct | Yes |
| `POST` | `/workspaces/{workspace_name}/chat/stream` | Streaming workspace chat — agent-direct only (SSE) | Yes |
| `POST` | `/workspaces/{workspace_name}/agents/` | Create an agent | Yes |
| `GET` | `/workspaces/{workspace_name}/agents/` | List agents in a workspace | Yes |
| `GET` | `/workspaces/{workspace_name}/agents/{agent_name}` | Get agent details | Yes |
| `PATCH` | `/workspaces/{workspace_name}/agents/{agent_name}` | Update agent config | Yes |
| `DELETE` | `/workspaces/{workspace_name}/agents/{agent_name}` | Delete an agent | Yes |
| `POST` | `/workspaces/{workspace_name}/agents/{agent_name}/chat` | Non-streaming agent chat | Yes |
| `POST` | `/workspaces/{workspace_name}/agents/{agent_name}/chat/stream` | Streaming agent chat (SSE) | Yes |
| `GET` | `/workspaces/{workspace_name}/conversations` | List conversations in a workspace | Yes |
| `GET` | `/workspaces/{workspace_name}/conversations/{id}/messages` | Get conversation message history | Yes |
| `GET` | `/workspaces/{workspace_name}/agents/{agent_name}/conversations` | List conversations (requires DB) | Yes |
| `DELETE` | `/workspaces/{workspace_name}/agents/{agent_name}/conversations/{id}` | Delete a conversation (requires DB) | Yes |

### Persistence
Async SQLAlchemy + asyncpg backed by PostgreSQL. ORM models live in `persistence/models.py`: `User`, `UserWorkspace`, `UserAgent`, `UserAPIKey`, `Conversation`, `Message`. Set `DATABASE_URL` to enable; omit it only when `AUTH_DISABLED=true` (in-memory dev mode). Use Alembic for migrations (`uv run alembic upgrade head`).

### Evaluation (optional)
DeepEval-based evaluation tests in `tests/evaluation/api/`. Tests use an Ollama-backed judge model (`qwen2.5:14b`) to evaluate LLM responses for relevancy, correctness, and toxicity. Run with `uv run pytest -m evaluation tests/evaluation/` (requires local Ollama at `http://localhost:11434`). Use `timeout=120.0` for LLM-backed requests.

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
uv run alembic upgrade head                    # Apply DB migrations
docker compose build                           # Build Docker image
docker compose up -d                           # Start app + postgres (detached)
```

## Conventions

- **New tools:** subclass `AssistantTool` in `personal_assistant/tools/`, define `name`, `description`, `args_schema` (Pydantic model), and `_run()`. To give a tool access to the calling agent's `AgentConfig`, add an `agent_config: AgentConfig | None = None` field — `Agent.register_tool` detects this via `model_fields` and injects a copy automatically via `model_copy`, so each agent gets its own bound instance and the original tool is never mutated.
- **New agents:** subclass `Agent` (see `career_agent.py`, `coding_agent.py`, `research_agent.py` for examples) or use `AgentConfig` directly with `orchestrator.create_agent()`. Use `AgentService` when calling from service/API layers.
- **New providers:** subclass `AIProvider` in `personal_assistant/providers/`, implement `get_model()`, register via `build_registry()` in `personal_assistant/bootstrap.py`.
- **New workspaces:** add a factory function in `personal_assistant/workspaces/`. Use `WorkspaceService` when calling from service/API layers.
- **New API endpoints:** add a router in `api/routers/`, include it in `api/main.py`, and add any new service exceptions to `api/exception_handlers.py`. Reuse or extend annotated path parameters from `api/routers/params.py`.
- Do not hardcode API keys or call `os.getenv` directly — use `get_settings()` from `personal_assistant.config`.
- Agent conversation history is cached per `(user_id, workspace_name, conversation_id)` in `InMemoryConversationCache`. The cache is automatically updated after each `run_agent` / `stream_agent` call. Call `AgentService.delete_conversation` to remove a conversation and invalidate its cache entry.
- `DATABASE_URL` is optional. When absent, the app runs fully in-memory with no persistence. Conversation list/delete endpoints return empty lists / 404 when no DB is configured.
- Service exceptions (`NotFoundError`, `AlreadyExistsError`, `ServiceValidationError`, `AuthError`, `ForbiddenError`) are in `services/exceptions.py` — catch these at API/CLI boundaries. `AuthError` maps to HTTP 401; `ForbiddenError` to 403.
- New auth flows: use `AuthService` (not raw token functions) from the service layer. `fork_default_workspace` is called automatically on registration — do not call it manually.
- Password hashing uses `pwdlib` with Argon2 (`auth/password.py`). JWT tokens use `PyJWT` with HS256 (`auth/tokens.py`). Do not use `passlib` or `python-jose`.
- All workspace/agent routes require `CurrentUserDep`. Services receive `user_id` and `session` as explicit arguments — they hold no per-user state.
- `AgentService` and `WorkspaceService` are **stateless singletons** created once at startup. Never add per-request or per-user state to them.
- Updating an agent rebuilds it entirely — there is no soft update path. Agent config changes (system prompt, model, allowed tools) may require a new LangGraph graph. Clients that need stateful conversations should not update agents mid-conversation.
