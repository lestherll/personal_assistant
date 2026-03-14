# Architecture

A modular AI personal assistant built on LangChain and LangGraph. Configurable agents specialise in specific tasks, are grouped into workspaces, and are backed by a pluggable provider registry. The system is fully functional in-memory; PostgreSQL persistence is additive and optional.

---

## Layered Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Entry Points                                            │
│  api/main.py (HTTP/FastAPI)   main.py (REPL)             │
├──────────────────────────────────────────────────────────┤
│  API Layer                                               │
│  Routers · Schemas · Dependencies · Exception Handlers   │
├──────────────────────────────────────────────────────────┤
│  Service Layer                                           │
│  AgentService · WorkspaceService · Views · Exceptions    │
├──────────────────────────────────────────────────────────┤
│  Core Domain                        Provider Registry    │
│  Orchestrator · Workspace ·         ProviderRegistry ·   │
│  Agent · AssistantTool              AIProvider           │
├──────────────────────────────────────────────────────────┤
│  Persistence (optional)                                  │
│  SQLAlchemy · ConversationRepository · ORM Models        │
└──────────────────────────────────────────────────────────┘
```

Each tier depends only on the tier directly below it. The API never touches the core domain directly — it always goes through the service layer.

---

## Layer Responsibilities

| Layer | Owns | Does not own |
|---|---|---|
| **API** | HTTP routing, request/response serialisation, DI wiring, HTTP error mapping | Business logic, domain state |
| **Service** | CRUD semantics, typed domain exceptions, domain-to-view projection | HTTP concerns, persistence details |
| **Core** | Agent lifecycle, workspace coordination, LLM orchestration, tool management | HTTP, serialisation, DB queries |
| **Providers** | LLM construction, provider-specific config | Agent state, tool registration |
| **Persistence** | DB schema, session management, message storage | Domain logic, agent lifecycle |

---

## Component Reference

### Providers

**`ProviderConfig`** — dataclass holding `name: str` and `default_model: str`. Subclassed by each concrete provider to add provider-specific fields (API key, temperature, base URL, etc.).

**`AIProvider`** — ABC with a single abstract method:
```python
def get_model(self, model: str | None = None, **kwargs) -> BaseChatModel
```
The `model` parameter falls back to `ProviderConfig.default_model` when `None`.

**`ProviderRegistry`** — named dictionary of `AIProvider` instances with a default pointer. The first registered provider becomes the default unless overridden. `get(name=None)` falls back to the default automatically.

**Concrete providers:**
- `AnthropicProvider` — wraps `ChatAnthropic`; reads `ANTHROPIC_API_KEY` from env.
- `OllamaProvider` — wraps `ChatOllama`; connects to local Ollama at `http://localhost:11434`.

**Extension point:** subclass `AIProvider`, implement `get_model()`, register with `registry.register(MyProvider())` in `api/main.py` or `main.py`.

---

### Core

#### `AssistantTool[R]`

Generic base class extending LangChain's `BaseTool`. Enforces:
- `name: str` — tool identifier
- `description: str` — shown to the LLM
- `args_schema: type[BaseModel]` — Pydantic v2 model for input validation
- `_run(**kwargs) -> R` — synchronous implementation

Default `_arun()` delegates to `_run()`. The generic `R` is the return type.

**Agent-config injection:** if a tool's Pydantic model has an `agent_config: AgentConfig | None = None` field, `Agent.register_tool()` detects this via `model_fields` and calls `tool.model_copy(update={"agent_config": self.config})` so each agent gets its own bound copy without mutating the shared tool instance.

#### `AgentConfig` + `Agent`

**`AgentConfig`** — pure-data record:

| Field | Type | Meaning |
|---|---|---|
| `name` | `str` | Identity key across all tiers |
| `description` | `str` | Purpose summary |
| `system_prompt` | `str` | LLM system message |
| `provider` | `str \| None` | Registry key; `None` → registry default |
| `model` | `str \| None` | Model name; `None` → provider default |
| `allowed_tools` | `list[str]` | Tool names this agent may use |

**`Agent`** — LangGraph ReAct agent. Key behaviours:

- **Lazy graph rebuild:** `register_tool()` / `remove_tool()` set `_dirty = True`. The LangGraph compiled graph is rebuilt at the next `run()` / `stream()` call via `_ensure_graph()`. `batch_tools()` is a context manager that defers the rebuild until exit.
- **Lazy history loading:** when `conversation_id` is set (resuming a conversation), history is NOT loaded from DB immediately. It is loaded on the first `run()` / `stream()` call with a valid session, gated by `_history_loaded`.
- **Factory classmethods:**
  - `Agent.from_config(config, registry)` — resolves provider + model from registry (normal path).
  - `Agent.from_llm(config, llm)` — bypasses registry; useful for testing with mock LLMs.

#### `WorkspaceConfig` + `Workspace`

**`WorkspaceConfig`** — dataclass: `name`, `description`, `metadata`.

**`Workspace`** — named container holding `dict[str, Agent]` and `dict[str, BaseTool]`.

Bidirectional propagation rules:
- Tool added to workspace → automatically registered with all existing agents.
- Agent added to workspace → automatically receives all existing workspace tools.
- `add_tool_to_agent()` registers a tool with one agent only; it does not appear in `list_tools()` and is not propagated to other agents.

#### `Orchestrator`

Central coordinator. Owns the `ProviderRegistry` and all `Workspace` instances.

| Method | Purpose |
|---|---|
| `create_workspace(config)` | Build and register a workspace |
| `add_workspace(ws)` | Register a pre-built workspace |
| `remove_workspace(name)` | Remove a workspace |
| `set_active_workspace(name)` | Change the default workspace |
| `create_agent(config, workspace_name)` | Build an `Agent` from config + registry, add to workspace |
| `replace_agent(config, workspace_name)` | Remove existing agent, create fresh one |
| `create_unmanaged_agent(config)` | Build an agent outside any workspace |
| `delegate(task, agent_name, workspace_name, session)` | Route a task to the named agent |

---

### Services

**`AgentService`** — stateless wrapper around `Orchestrator` for agent operations:
- CRUD: `create_agent`, `list_agents`, `get_agent`, `update_agent`, `delete_agent`
- Chat: `run_agent`, `stream_agent`, `reset_agent`
- `update_agent()` rebuilds the agent from a merged config (conversation history is lost — see [Design Decisions](#key-design-decisions)).

**`WorkspaceService`** — stateless wrapper for workspace operations:
- CRUD: `create_workspace`, `list_workspaces`, `get_workspace`, `update_workspace`, `delete_workspace`
- `update_workspace()` mutates `ws.config` in-place (safe because no structural rebuild is needed).

**`schemas.py`** — Pydantic v2 request DTOs: `CreateAgentRequest`, `UpdateAgentRequest`, `ChatRequest`, `CreateWorkspaceRequest`, `UpdateWorkspaceRequest`.

**`views.py`** — frozen dataclass response projections: `AgentView`, `WorkspaceView`, `WorkspaceDetailView`. No logic — pure data for serialisation.

**`exceptions.py`** — typed domain exceptions:

| Exception | HTTP mapping | Attributes |
|---|---|---|
| `NotFoundError` | 404 | `kind`, `name` |
| `AlreadyExistsError` | 409 | `kind`, `name` |
| `ServiceValidationError` | 422 | `message` |

---

### API

**`api/main.py`** — FastAPI lifespan bootstrap:
1. Build `ProviderRegistry`, register `AnthropicProvider` and `OllamaProvider`.
2. Create `Orchestrator(registry)`, store on `app.state`.
3. Call workspace factory, add default workspace to orchestrator.
4. If `DATABASE_URL` is set: `build_engine()` → `build_session_factory()` → store on `app.state`.
5. On shutdown: dispose engine if present.

**`api/dependencies.py`** — request-scoped DI:
- `get_orchestrator(request)` — returns `app.state.orchestrator` (no allocation).
- `get_workspace_service(orchestrator)` — constructs `WorkspaceService` per request.
- `get_agent_service(orchestrator)` — constructs `AgentService` per request.
- `get_db_session(request)` — yields `AsyncSession | None` (graceful no-DB degradation).

**`api/routers/workspaces.py`** — `/workspaces` CRUD.

**`api/routers/agents.py`** — `/workspaces/{workspace_name}/agents` CRUD + chat:
- `POST /{agent_name}/chat` — non-streaming, returns `ChatResponse`.
- `POST /{agent_name}/chat/stream` — SSE streaming, `text/event-stream`.
- `POST /{agent_name}/reset` — clears conversation history.

**`api/exception_handlers.py`** — registers handlers mapping service exceptions → HTTP responses with `ErrorResponse(error, detail)` body.

**`api/schemas.py`** — Pydantic response DTOs with `from_view()` factory methods that consume service-layer view dataclasses. Separate from service schemas to keep serialisation and OpenAPI docs out of the service layer.

---

### Persistence (optional)

**`database.py`** — two factory functions: `build_engine(url)` and `build_session_factory(engine)`. No global state.

**`models.py`** — SQLAlchemy 2 ORM models:
- `Conversation` — `agent_name`, `workspace_name` (denormalised strings), `created_at`, `updated_at`.
- `Message` — `role` (`"human"` | `"ai"`), `Text` content, optional `JSONB extra_metadata`.

**`repository.py`** — `ConversationRepository`: explicit-transaction async data-access layer. Instantiated inline inside `Agent.run()` / `Agent.stream()` when a session is provided.

---

## Key Design Decisions

### Lazy graph rebuild (`_dirty` flag)
LangGraph compiles a graph from the LLM and tool list. Recompiling on every `register_tool` call would be expensive. Instead, the flag is set on any tool change and the graph is (re)built only at the next inference call via `_ensure_graph()`. `batch_tools()` makes bulk tool operations a single rebuild.

### Lazy history loading
Setting `agent.conversation_id` to resume a conversation is a cheap assignment. The DB round-trip to load history happens only on the first `run()` / `stream()` call that actually needs it, gated by `_history_loaded`. This avoids unnecessary queries when, for example, introspecting an agent without running it.

### Tool config-injection via `model_copy()`
Tools that declare `agent_config: AgentConfig | None = None` receive an agent-specific copy via `model_copy(update={...})` at registration time. The shared tool instance is never mutated, so the same tool object can be registered with multiple agents and each gets its own bound instance. This allows tools to introspect their owning agent without creating bidirectional coupling.

### Bidirectional tool propagation in `Workspace`
The workspace is the unit of tool coordination. When a tool is added to a workspace it is propagated to all current agents; when an agent joins a workspace it receives all current tools. This means agents never need direct references to each other, and tool lifecycle is managed in one place.

### Optional persistence — additive, not intrusive
The `AsyncSession | None` pattern in `agent.run()` / `agent.stream()` means the entire call path works with `None`. No core logic is conditional on persistence availability except for explicit `if session:` guards. The system runs fully in-memory without any database configuration.

### Request-scoped services
`AgentService` and `WorkspaceService` are constructed fresh per request. The `Orchestrator` on `app.state` is the only application-scoped mutable state. Services are stateless wrappers; there is no shared mutable state between requests, so no locking is needed at the service level.

### View + Response DTO split
- **Service views** (`AgentView`, `WorkspaceView`, etc.) are plain frozen dataclasses — easy to construct in tests, carry no serialisation logic.
- **API response schemas** (`AgentResponse`, `WorkspaceResponse`, etc.) handle Pydantic serialisation and OpenAPI doc generation via `from_view()` factory methods.

This keeps the service layer fully decoupled from FastAPI/Pydantic response concerns.

### SSE streaming with plain-text tokens + `[DONE]` sentinel
Streaming responses emit `data: {token}\n\n` lines and terminate with `data: [DONE]\n\n`. Using raw text tokens (not JSON-wrapped objects) keeps client parsing trivial. The agent existence check (`service.get_agent()`) runs before the generator starts so that 404 errors are returned as proper HTTP responses, not embedded in the event stream.

### Agent update resets conversation history
`update_agent()` replaces the agent entirely via `orchestrator.replace_agent()`. There is no "soft update" path. This is intentional: agent config changes (system prompt, model, allowed tools) may require a new LangGraph graph, and the simplest correct approach is a full rebuild. Clients that need stateful conversations should not update agents mid-conversation.

---

## Data Flow Diagrams

### 1. Startup Bootstrap

```
api/main.py lifespan start
  │
  ├─ ProviderRegistry()
  │    ├─ register(AnthropicProvider())
  │    └─ register(OllamaProvider())  ← set as default
  │
  ├─ Orchestrator(registry)  →  app.state.orchestrator
  │
  ├─ create_default_workspace(orchestrator)
  │    └─ workspace factory: WorkspaceConfig → Workspace
  │         └─ AssistantAgent.create() → AgentConfig → Agent.from_config(registry)
  │              └─ registry.get(provider) → AIProvider.get_model(model) → BaseChatModel
  │
  └─ if DATABASE_URL:
       ├─ build_engine(url)  →  AsyncEngine
       ├─ build_session_factory(engine)  →  async_sessionmaker
       └─ app.state.session_factory = session_factory
```

### 2. Non-Streaming Chat

```
POST /workspaces/{workspace_name}/agents/{agent_name}/chat
  { "message": "Hello" }
  │
  ├─ Pydantic validates body → ChatRequest
  ├─ DI: get_agent_service → AgentService(orchestrator)
  ├─ DI: get_db_session → AsyncSession | None
  │
  └─ AgentService.run_agent(workspace_name, agent_name, message, session)
       ├─ _get_workspace_or_raise()  → Workspace  (NotFoundError on miss)
       ├─ _get_agent_or_raise()      → Agent      (NotFoundError on miss)
       └─ agent.run(message, session)
            ├─ _ensure_graph()      ← rebuild LangGraph if _dirty
            ├─ _ensure_history_loaded(session)  ← DB fetch if session + not loaded
            ├─ append HumanMessage to _history
            ├─ graph.ainvoke({"messages": _history})
            │    └─ ReAct loop:
            │         LLM call → [tool calls?] → tool execution → LLM call → AIMessage
            ├─ update _history with result messages
            └─ return last message content (str)
       └─ return AgentView (not used directly for chat)
  │
  └─ ChatResponse(reply=response)  →  { "reply": "Hello! ..." }
```

### 3. Streaming Chat

```
POST /workspaces/{workspace_name}/agents/{agent_name}/chat/stream
  { "message": "Hello" }
  │
  ├─ service.get_agent(workspace_name, agent_name)  ← validates existence first
  │    └─ NotFoundError → 404 (before StreamingResponse headers are sent)
  │
  └─ StreamingResponse(generate(), media_type="text/event-stream")
       └─ generate():
            └─ agent.stream(message, session)
                 ├─ _ensure_graph()
                 ├─ _ensure_history_loaded(session)
                 ├─ append HumanMessage
                 ├─ graph.astream({"messages": _history})
                 │    └─ for each token chunk:
                 │         yield  "data: {token}\n\n"
                 └─ yield  "data: [DONE]\n\n"
```

---

## Endpoint Reference

| Method | Path | Description | Status |
|---|---|---|---|
| `GET` | `/health` | Health check | 200 |
| `POST` | `/workspaces` | Create a workspace | 201 |
| `GET` | `/workspaces` | List all workspaces | 200 |
| `GET` | `/workspaces/{workspace_name}` | Get workspace details | 200 |
| `PATCH` | `/workspaces/{workspace_name}` | Update workspace metadata | 200 |
| `DELETE` | `/workspaces/{workspace_name}` | Delete a workspace | 204 |
| `POST` | `/workspaces/{workspace_name}/agents` | Create an agent | 201 |
| `GET` | `/workspaces/{workspace_name}/agents` | List agents in workspace | 200 |
| `GET` | `/workspaces/{workspace_name}/agents/{agent_name}` | Get agent details | 200 |
| `PATCH` | `/workspaces/{workspace_name}/agents/{agent_name}` | Update agent config | 200 |
| `DELETE` | `/workspaces/{workspace_name}/agents/{agent_name}` | Delete an agent | 204 |
| `POST` | `/workspaces/{workspace_name}/agents/{agent_name}/chat` | Non-streaming chat | 200 |
| `POST` | `/workspaces/{workspace_name}/agents/{agent_name}/chat/stream` | Streaming chat (SSE) | 200 |
| `POST` | `/workspaces/{workspace_name}/agents/{agent_name}/reset` | Reset conversation history | 200 |

---

## Extension Guide

### Add a new AI provider

1. Create `personal_assistant/providers/my_provider.py`:
   ```python
   from personal_assistant.providers.base import AIProvider, ProviderConfig
   from langchain_core.language_models import BaseChatModel

   class MyProviderConfig(ProviderConfig):
       api_key: str

   class MyProvider(AIProvider):
       def __init__(self, config: MyProviderConfig | None = None) -> None:
           self.config = config or MyProviderConfig(name="my_provider", default_model="my-model")

       def get_model(self, model: str | None = None, **kwargs) -> BaseChatModel:
           return MyLangChainModel(model=model or self.config.default_model, **kwargs)
   ```
2. Register in `api/main.py` (and `main.py` for REPL):
   ```python
   registry.register(MyProvider())
   ```

### Add a new tool

1. Create `personal_assistant/tools/my_tool.py`:
   ```python
   from pydantic import BaseModel
   from personal_assistant.core.tool import AssistantTool

   class MyToolInput(BaseModel):
       query: str

   class MyTool(AssistantTool[str]):
       name = "my_tool"
       description = "Does something useful."
       args_schema = MyToolInput

       def _run(self, query: str) -> str:
           return f"result for {query}"
   ```
2. Add to a workspace via `workspace.add_tool(MyTool())` or `orchestrator.get_workspace("name").add_tool(MyTool())`.

   To give the tool access to its owning agent, add `agent_config: AgentConfig | None = None` to the input schema — the agent will inject a copy automatically.

### Add a new agent

Use `AgentConfig` directly or subclass `Agent`:

```python
from personal_assistant.core.agent import AgentConfig
from personal_assistant.services.agent_service import AgentService

config = AgentConfig(
    name="my_agent",
    description="Specialist agent.",
    system_prompt="You are a specialist in ...",
    provider="anthropic",  # or None for registry default
    model="claude-sonnet-4-6",
)
# Via service (recommended from API/CLI contexts):
agent_view = await agent_service.create_agent(workspace_name, config)

# Via orchestrator directly:
orchestrator.create_agent(config, workspace_name="default")
```

### Add a new workspace factory

1. Create `personal_assistant/workspaces/my_workspace.py`:
   ```python
   from personal_assistant.core.orchestrator import Orchestrator
   from personal_assistant.core.workspace import Workspace, WorkspaceConfig

   def create_my_workspace(orchestrator: Orchestrator) -> Workspace:
       ws = Workspace(WorkspaceConfig(name="my_workspace", description="..."))
       # add agents and tools
       orchestrator.add_workspace(ws)
       return ws
   ```
2. Call the factory in `api/main.py` lifespan after the orchestrator is created.

### Add a new API endpoint

1. Add the route to the appropriate router in `api/routers/`:
   ```python
   @router.post("/{agent_name}/my_action", status_code=200)
   async def my_action(
       workspace_name: str,
       agent_name: str,
       service: AgentService = Depends(get_agent_service),
   ) -> MyResponse:
       result = await service.my_operation(workspace_name, agent_name)
       return MyResponse.from_view(result)
   ```
2. Add the corresponding method to `AgentService` or `WorkspaceService`.
3. If a new exception type is introduced, register a handler in `api/exception_handlers.py`.
