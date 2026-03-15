# Personal Assistant — Copilot Instructions

This is a modular AI personal assistant built on LangChain and LangGraph, with configurable agents, pluggable providers, and an optional PostgreSQL backend. You are helping improve the codebase.

## Essential Context

**Stack**: Python 3.13, LangChain/LangGraph, FastAPI, SQLAlchemy (async), pydantic v2, pytest.

**Architecture**: 5-tier layered design (API → Services → Core Domain → Providers → Persistence). Each tier depends only on the tier below.

**Build/Run Commands**:
```bash
uv sync                             # Install dependencies
uv run python main.py               # Interactive REPL
uv run fastapi dev api/main.py      # REST API (auto-reload on port 8000)
uv run pytest                       # Unit + functional tests (skip evaluation)
uv run ruff check . && uv run ruff format .   # Lint and format
uv run mypy . --exclude tests       # Type-check (strict mode)
```

**Key Files**:
- [CLAUDE.md](CLAUDE.md) — Project overview, stack, conventions, all endpoints
- [ARCHITECTURE.md](ARCHITECTURE.md) — Detailed layer diagram
- [personal_assistant/bootstrap.py](personal_assistant/bootstrap.py) — Registry setup (called by REPL + API)
- [api/main.py](api/main.py) — FastAPI app, lifespan bootstrap, service instantiation
- [pyproject.toml](pyproject.toml) — Dependencies, pytest config, ruff rules, mypy strict mode

**Environment**: Copy `.env.example` → `.env`; set `ANTHROPIC_API_KEY`, optionally `RAPIDAPI_KEY` and `DATABASE_URL`. Set `AUTH_DISABLED=true` for in-memory dev mode (no DB required).

---

## Architecture Quick Reference

### 1. **Providers** — Pluggable LLM Backends
- Central `ProviderRegistry` (keyed by name) registered at startup in `build_registry()`
- **Anthropic** (`claude-opus`, `claude-sonnet`, `claude-haiku`) — Set via `ANTHROPIC_API_KEY`
- **Ollama** (local models, default `qwen2.5:14b`) — Runs at `http://localhost:11434`
- Each provider wraps a LangChain `BaseChatModel` and exposes `get_model(name)` + `async list_models()`

**Files**: [providers/registry.py](personal_assistant/providers/registry.py), [providers/base.py](personal_assistant/providers/base.py), [providers/anthropic.py](personal_assistant/providers/anthropic.py), [providers/ollama.py](personal_assistant/providers/ollama.py)

### 2. **Agents** — Configurable LLM Specialists
- Defined by `AgentConfig` (name, description, system_prompt, provider, model, allowed_tools)
- Build LangGraph ReAct loop that manages conversation history and tool calls
- Maintain `_history: list[BaseMessage]` (restored per-request from cache or DB)
- Four built-in agents: `assistant`, `career`, `coding`, `research` (lazy-loaded from `DEFAULT_AGENTS` dict)

**Creation pattern**:
```python
class MyAgent(Agent):
    @classmethod
    def create(cls, registry: ProviderRegistry) -> "MyAgent":
        config = AgentConfig(name="MyAgent", description="...", system_prompt="...")
        return cls(config, registry)
```

**Files**: [core/agent.py](personal_assistant/core/agent.py), [agents/](personal_assistant/agents/) (examples)

### 3. **Tools** — Agent Actions
- Inherit from `AssistantTool[ReturnType]`, define `name`, `description`, `args_schema` (Pydantic), `_run()`
- **Magic feature**: If tool has `agent_config: AgentConfig | None = None` field, `Agent.register_tool()` injects a bound copy per agent via `model_copy()` — no shared state
- Auto-registered with compatible agents in a workspace

**Pattern**:
```python
from personal_assistant.core.tool import AssistantTool
from pydantic import BaseModel, Field

class MyToolInput(BaseModel):
    param: str = Field(description="...")

class MyTool(AssistantTool[str]):
    name = "my_tool"
    description = "..."
    args_schema = MyToolInput
    agent_config: AgentConfig | None = None  # Injected per-agent
    
    def _run(self, param: str) -> str:
        # Use self.agent_config if needed
        return f"Result: {param}"
```

**Files**: [core/tool.py](personal_assistant/core/tool.py), [tools/example_tool.py](personal_assistant/tools/example_tool.py) (with examples)

### 4. **Workspaces** — Multi-Agent Containers
- Group agents + tools together
- Tools added to workspace auto-register with all compatible agents
- Includes `WorkspaceSupervisor` (LangGraph StateGraph) that routes messages to best agent
- Two chat modes: **supervisor** (automatic routing), **agent-direct** (specified by name)

**File**: [core/workspace.py](personal_assistant/core/workspace.py)

### 5. **Services** — Stateless CRUD + Domain Logic
- **Key principle**: Singletons, no per-user state. Always pass `user_id`, `workspace_name`, `conversation_id`, `session` explicitly
- **AgentService**: `create_agent()`, `list_agents()`, `run_agent()`, `stream_agent()`, conversation management
- **WorkspaceService**: `create_workspace()`, `chat()` (supervisor or agent-direct), `stream_chat()`
- **AuthService**: `register()`, `login()`, `refresh()`, JWT lifecycle
- **Exception mapping**: Service exceptions (`NotFoundError`, `AlreadyExistsError`, `ServiceValidationError`, `AuthError`, `ForbiddenError`) → HTTP status codes via [api/exception_handlers.py](api/exception_handlers.py)

**Files**: [services/agent_service.py](personal_assistant/services/agent_service.py), [services/workspace_service.py](personal_assistant/services/workspace_service.py), [services/auth_service.py](personal_assistant/services/auth_service.py)

### 6. **Persistence (Optional)** — SQLAlchemy + asyncpg
- ORM models: `User`, `UserWorkspace`, `UserAgent`, `Conversation`, `Message`
- Repositories: `ConversationRepository`, `UserRepository`, `UserWorkspaceRepository`
- Optional: Set `DATABASE_URL` to enable. Omit it (with `AUTH_DISABLED=true`) for fully in-memory mode
- Conversation cache (`InMemoryConversationCache`, keyed by `(user_id, workspace_name, conversation_id)`) auto-updated after agent runs

**Files**: [persistence/models.py](personal_assistant/persistence/models.py), [persistence/database.py](personal_assistant/persistence/database.py), [persistence/repository.py](personal_assistant/persistence/repository.py)

### 7. **API Layer** — FastAPI Routers
- Lifespan bootstrap: env check → registry → orchestrator → services (singletons on app.state)
- DI extracts current user, session, services; routers call service methods
- Exception handlers map domain exceptions to HTTP responses

**Routers**:
- [api/routers/auth.py](api/routers/auth.py) — register, login, refresh (public)
- [api/routers/workspaces.py](api/routers/workspaces.py) — workspace CRUD + chat (supervisor/agent-direct)
- [api/routers/agents.py](api/routers/agents.py) — agent CRUD + chat/stream within workspace
- [api/routers/providers.py](api/routers/providers.py) — provider discovery
- [api/routers/health.py](api/routers/health.py) — `GET /health`

**Files**: [api/main.py](api/main.py), [api/dependencies.py](api/dependencies.py), [api/exception_handlers.py](api/exception_handlers.py)

---

## Coding Conventions

### Tools
- **New tool**: Subclass `AssistantTool[R]` in [personal_assistant/tools/](personal_assistant/tools/), define `name`, `description`, `args_schema`, `_run()`
- **Agent-specific config**: Add `agent_config: AgentConfig | None = None` field; auto-injected per-agent
- **Registration**: `workspace.add_tool(tool)` (all agents), or `workspace.add_tool_to_agent(agent_name, tool)` (single agent)
- **Tests**: Mock tool behavior in unit tests; functional tests verify tool calls work end-to-end

### Agents
- **New agent**: Subclass `Agent` with `.create(registry)` classmethod, OR use `AgentConfig` directly with `Agent(config, registry)`
- **Registration**: Add to [agents/__init__.py](personal_assistant/agents/__init__.py) `DEFAULT_AGENTS` dict as lazy factory
- **System prompt**: Describe agent's role, available tools, expected input/output format
- **Tool allowlist**: Set `allowed_tools` in `AgentConfig`; agent only sees whitelisted tools

### Providers
- **New provider**: Subclass `AIProvider`, implement `get_model(name) → BaseChatModel`, optionally override `async list_models() → list[str]`
- **Registration**: Add to `build_registry()` in [personal_assistant/bootstrap.py](personal_assistant/bootstrap.py)
- **Model discovery**: Override `list_models()` to return available models (e.g., Ollama queries `/api/tags`)

### Workspaces
- **Factory pattern**: Add function to [personal_assistant/workspaces/](personal_assistant/workspaces/) that returns configured `Workspace`
- **Default workspace**: Pre-loads 4 agents + common tools; forked to new users on registration

### API Endpoints
- **DI pattern**: Use `CurrentUserDep`, `DbSessionDep`, service getters from [api/dependencies.py](api/dependencies.py)
- **Exception handling**: Raise service exceptions (`NotFoundError`, etc.); exception handlers do HTTP mapping
- **Streaming**: Return `StreamingResponse` with SSE format (`data: {chunk}\n\n`)

### Services
- **Stateless singletons**: Never store per-user, per-request, or per-conversation state
- **Explicit parameters**: Pass `user_id`, `workspace_name`, `conversation_id`, `session` always
- **DB sessions**: Accept `session: AsyncSession | None = None`; repos use it for transactional operations
- **Exceptions**: Define in [services/exceptions.py](personal_assistant/services/exceptions.py), raise with clear messages

---

## Testing Patterns

**Unit Tests** ([tests/unit/](tests/unit/)) — Mock-based, no real server
- Fixtures: [tests/unit/conftest.py](tests/unit/conftest.py) (`mock_provider`, `mock_registry`, `agent`, `make_mock_graph`)
- Test structure: `test_*_returns_*`, `test_*_calls_*` (what it returns, what it calls)
- Mocking: Use `pytest-mock` (`mocker` fixture) to mock LangChain graphs, DB repos, external APIs

**Functional Tests** ([tests/functional/api/](tests/functional/api/)) — Real server, real HTTP
- Sets `AUTH_DISABLED=true` before importing API
- Fixture `live_server_url` starts Uvicorn in background thread
- Uses `httpx.AsyncClient` to make real HTTP requests
- No mocking; exercises full stack

**Evaluation Tests** ([tests/evaluation/](tests/evaluation/)) — LLM-judged responses
- Marked with `@pytest.mark.evaluation` (skipped by default)
- Requires local Ollama at `http://localhost:11434`
- Run separately: `uv run pytest -m evaluation tests/evaluation/`

**Coverage**: Minimum 85% enforced. Run `uv run pytest --cov` to check.

---

## Common Pitfalls

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Agent LangGraph not updating | LangGraph rebuilt when tools added/removed; rebuilds are expensive | Don't update agent tools mid-conversation; recreate agent if needed |
| `model_copy()` fails on tool | Tool not a Pydantic model; can't be copied with field updates | Ensure tool inherits from `AssistantTool` (which is a `BaseModel`) |
| mypy reports implicit Any | Type-checking runs in strict mode; all functions must be typed | Add type hints to all parameters/returns; use `type: ignore` comment if justified |
| App crashes at startup | Missing `DATABASE_URL` when `AUTH_DISABLED=false` | Set `DATABASE_URL` OR set `AUTH_DISABLED=true` for dev/test mode |
| Services losing user context | Services are singletons; stateful code causes cross-user bugs | Always pass `user_id`, `workspace_name`, `session` explicitly; never store in self |
| Hardcoded secrets committed | CI bandit scanning catches secrets | Load all APIs keys/passwords from `.env`; never commit credentials |
| In-memory cache lost on restart | `InMemoryConversationCache` ephemeral | Conversation history is also in DB; cache is optimization layer |
| Exception not mapped to HTTP | Only service-layer exceptions have HTTP handlers | Raise `NotFoundError`, etc. in service layer, not routers |
| Supervisor returns invalid agent name | LLM hallucination; falls back to first agent in list | Validate agent names; ensure all workspace agents are reachable |
| Wrong token format | JWT scheme is case-sensitive: `Authorization: Bearer <token>` | Use exact format; test with `oauth2_scheme` mock |
| Tool not available in agent | Tool allowed_tools list doesn't include it | Check `AgentConfig.allowed_tools`; add tool name if needed; re-register agent |

---

## Extension Guide — How to Add Things

### Add a New Tool
1. Create file [personal_assistant/tools/my_tool.py](personal_assistant/tools/my_tool.py)
2. Subclass `AssistantTool[ReturnType]`, define `name`, `description`, `args_schema`, `_run()`
3. Optional: Add `agent_config: AgentConfig | None = None` for per-agent customization
4. Add unit test in [tests/unit/tools/test_my_tool.py](tests/unit/tools/test_my_tool.py)
5. Register in workspace: `workspace.add_tool(MyTool())` or `workspace.add_tool_to_agent(agent_name, MyTool())`

### Add a New Agent
1. Create file [personal_assistant/agents/my_agent.py](personal_assistant/agents/my_agent.py)
2. Subclass `Agent` or use `AgentConfig` directly
3. Add `.create(registry: ProviderRegistry)` classmethod
4. Add to [personal_assistant/agents/__init__.py](personal_assistant/agents/__init__.py) `DEFAULT_AGENTS` dict
5. Wire into [personal_assistant/workspaces/default_workspace.py](personal_assistant/workspaces/default_workspace.py)
6. Add unit tests in [tests/unit/core/test_agent.py](tests/unit/core/test_agent.py) or new file

### Add a New Provider
1. Create file [personal_assistant/providers/my_provider.py](personal_assistant/providers/my_provider.py)
2. Subclass `AIProvider`, implement `get_model(name) → BaseChatModel`
3. Override `async list_models() → list[str]` if applicable
4. Add to `build_registry()` in [personal_assistant/bootstrap.py](personal_assistant/bootstrap.py): `registry.register(MyProvider())`
5. Add unit tests in [tests/unit/providers/test_my_provider.py](tests/unit/providers/test_my_provider.py)

### Add an API Endpoint
1. Create router file [api/routers/my_feature.py](api/routers/my_feature.py) (or extend existing)
2. Use DI: `CurrentUserDep`, service getters from [api/dependencies.py](api/dependencies.py)
3. Call service methods in function body
4. Raise service exceptions (`NotFoundError`, etc.); exception handlers map to HTTP
5. Include in [api/main.py](api/main.py): `app.include_router(my_feature.router)`
6. Add unit tests [tests/unit/api/test_my_feature_router.py](tests/unit/api/test_my_feature_router.py)
7. Add functional tests [tests/functional/api/test_my_feature.py](tests/functional/api/test_my_feature.py)

### Add a Service Exception
1. Define in [personal_assistant/services/exceptions.py](personal_assistant/services/exceptions.py)
2. Add handler in [api/exception_handlers.py](api/exception_handlers.py) mapping to HTTP status code
3. Raise in service layer; never catch and re-raise in routers

---

## Code Quality

**Linting & Formatting**:
```bash
uv run ruff check .          # Check (E, W, F, I, UP, B, C4, RUF; ignores B008)
uv run ruff format .         # Format (double quotes, space indent)
```

**Type Checking** (strict mode):
```bash
uv run mypy . --exclude tests
```
All functions must have type hints; no implicit `Any`. Use `# type: ignore` only when justified.

**Testing** (85% coverage minimum):
```bash
uv run pytest                      # Unit + functional (skip evaluation)
uv run pytest --cov               # Show coverage
```

**Pre-commit hooks** ([.pre-commit-config.yaml](.pre-commit-config.yaml)):
- `ruff format`, `ruff check`, `mypy`, `pytest`

---

## Useful References

- [CLAUDE.md](CLAUDE.md) — Full project overview, stack, conventions, all endpoints
- [ARCHITECTURE.md](ARCHITECTURE.md) — Detailed layer responsibilities
- [pyproject.toml](pyproject.toml) — Dependencies, pytest config, ruff/mypy settings
- [.env.example](.env.example) — Environment variables
- `.pre-commit-config.yaml` — CI checks (format, lint, type-check, test)
