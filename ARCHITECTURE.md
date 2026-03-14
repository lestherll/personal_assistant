# Architecture

A modular AI personal assistant built on LangChain and LangGraph. Configurable agents specialise in specific tasks, are grouped into workspaces, and are backed by a pluggable provider registry. The system is fully functional in-memory; PostgreSQL persistence is additive and optional.

---

## Layered Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Entry Points                                            │
│  HTTP/FastAPI server          REPL                       │
├──────────────────────────────────────────────────────────┤
│  API Layer                                               │
│  Routers · Schemas · Dependencies · Exception Handlers   │
├──────────────────────────────────────────────────────────┤
│  Service Layer                                           │
│  AgentService · WorkspaceService · ConversationService   │
│  ConversationPool · Views · Exceptions                   │
├──────────────────────────────────────────────────────────┤
│  Core Domain                        Provider Registry    │
│  Orchestrator · Workspace ·         ProviderRegistry ·   │
│  WorkspaceSupervisor · Agent ·      AIProvider           │
│  AssistantTool                                           │
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
| **Service** | CRUD semantics, typed domain exceptions, domain-to-view projection, conversation clone lifecycle | HTTP concerns, persistence details |
| **Core** | Agent lifecycle, workspace coordination, supervisor routing, LLM orchestration, tool management | HTTP, serialisation, DB queries |
| **Providers** | LLM construction, provider-specific config | Agent state, tool registration |
| **Persistence** | DB schema, session management, message storage | Domain logic, agent lifecycle |

---

## Component Reference

### Providers

**`ProviderConfig`** — dataclass holding `name: str` and `default_model: str`. Subclassed by each concrete provider to add provider-specific fields (API key, temperature, base URL, etc.).

**`AIProvider`** — ABC with one abstract method and one async method:
```python
def get_model(self, model: str | None = None, **kwargs) -> BaseChatModel
async def list_models(self) -> list[str]   # default: [self.default_model]
```
The `model` parameter of `get_model` falls back to `ProviderConfig.default_model` when `None`. `list_models` has a default implementation that returns `[default_model]`; subclasses override it to expose the full model catalogue.

**`ProviderRegistry`** — named dictionary of `AIProvider` instances with a default pointer. The first registered provider becomes the default unless overridden. `get(name=None)` falls back to the default automatically.

**Concrete providers:**
- `AnthropicProvider` — wraps `ChatAnthropic`; reads `ANTHROPIC_API_KEY` from env. `list_models()` returns a hardcoded list of known Claude model IDs.
- `OllamaProvider` — wraps `ChatOllama`; connects to local Ollama at `http://localhost:11434`. `list_models()` queries `GET /api/tags` via `httpx` and falls back to `[default_model]` on any error.

**Extension point:** subclass `AIProvider`, implement `get_model()` (and optionally `list_models()`), register with `registry.register(MyProvider())` in the app bootstrap.

---

### Core

#### `AssistantTool[R]`

Generic base class extending LangChain's `BaseTool`. Enforces:
- `name: str` — tool identifier
- `description: str` — shown to the LLM
- `args_schema: type[BaseModel]` — Pydantic v2 model for input validation
- `_run(**kwargs) -> R` — synchronous implementation

Default `_arun()` delegates to `_run()`. The generic `R` is the return type.

**Agent-config injection:** if a tool's Pydantic model has an `agent_config: AgentConfig | None = None` field, the agent detects this via `model_fields` at registration time and binds an agent-specific copy via `model_copy(update={...})` so each agent gets its own instance without mutating the shared tool.

#### `AgentConfig` + `Agent`

**`AgentConfig`** — pure-data record:

| Field | Type | Meaning |
|---|---|---|
| `name` | `str` | Identity key across all tiers |
| `description` | `str` | Purpose summary (also used by the supervisor for routing) |
| `system_prompt` | `str` | LLM system message |
| `provider` | `str \| None` | Registry key; `None` → registry default |
| `model` | `str \| None` | Model name; `None` → provider default |
| `allowed_tools` | `list[str]` | Tool names this agent may use |

**`Agent`** — LangGraph ReAct agent. Key behaviours:

- **Lazy graph rebuild:** `register_tool()` / `remove_tool()` set `_dirty = True`. The LangGraph compiled graph is rebuilt at the next `run()` / `stream()` call via `_ensure_graph()`. `batch_tools()` is a context manager that defers the rebuild until exit.
- **Lazy history loading:** when `conversation_id` is set (resuming a conversation), history is NOT loaded from DB immediately. It is loaded on the first `run()` / `stream()` call with a valid session, gated by `_history_loaded`.
- **Cloning:** `agent.clone(*, llm=None)` produces a fresh agent with the same config and tools but empty history. The optional `llm` kwarg substitutes a different LLM in the clone without modifying the template. Used by `ConversationService` to give each conversation its own isolated agent instance, and to create ephemeral per-turn clones when a model override is requested.
- **Factory classmethods:**
  - `Agent.from_config(config, registry)` — resolves provider + model from registry (normal path).
  - `Agent.from_llm(config, llm)` — bypasses registry; useful for testing with mock LLMs.

**Specialised agents** (subclasses of `Agent`) ship as ready-to-use presets with a `create(registry)` classmethod:
- `AssistantAgent` — general-purpose starter agent.
- `PythonCodingAgent` — Python coding, debugging, and code review.
- `GeneralResearchAgent` — article summarisation and question answering.
- `CareerAgent` — resume review, cover letters, and interview preparation.

#### `WorkspaceConfig` + `Workspace`

**`WorkspaceConfig`** — dataclass: `name`, `description`, `metadata`.

**`Workspace`** — named container holding agents and tools, plus a lazily-initialised supervisor.

Bidirectional propagation rules:
- Tool added to workspace → automatically registered with all existing agents.
- Agent added to workspace → automatically receives all existing workspace tools.
- Agent-private tools can be registered to a single agent without entering the shared workspace tool registry and without propagating to other agents.

Mutation rules:
- `add_agent` raises `ValueError` on name collision — use `replace_agent` to swap.
- `remove_agent` and `remove_tool` raise `KeyError` if the name is not present.

Whenever the agent roster changes (add, remove, replace) the workspace rebuilds its supervisor automatically.

#### `WorkspaceSupervisor`

Builds and owns a LangGraph `StateGraph` that routes workspace-level chat to the most suitable agent. The graph has one node per agent plus a supervisor node that uses an LLM to decide which agent handles the next turn.

- **Conversation threading:** state is persisted across turns by LangGraph's `MemorySaver` checkpointer, keyed by `thread_id`. Callers pass a `thread_id` to resume a conversation; a new UUID is generated when none is provided.
- **Routing logic:** the supervisor LLM inspects agent `name` + `description` fields and the conversation so far, then emits a structured decision. If the decision is invalid it falls back to the first agent.
- **Return value:** `run(message, thread_id)` → `(response_text, thread_id, agent_used)`. The caller always gets back the `thread_id` so it can be included in the response and reused on the next turn.
- **Rebuilding:** `rebuild(agents)` re-compiles the graph when the agent roster changes. Called automatically by `Workspace`.

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

**`AgentService`** — stateless wrapper around the orchestrator for agent operations:
- CRUD: create, list, get, update, delete agents.
- Chat: run (non-streaming), stream (SSE), reset conversation history.
- Conversation lifecycle: list conversations, delete a conversation (both require a DB session).
- `update_agent()` rebuilds the agent from a merged config (conversation history is lost — see [Design Decisions](#key-design-decisions)).

**`WorkspaceService`** — stateless wrapper for workspace operations. Requires a `ConversationService` for the agent-direct chat paths.
- CRUD: create, list, get, update, delete workspaces.
- `chat(workspace_name, message, conversation_id, agent_name, provider, model, session)` — two routing modes:
  - **Supervisor path** (`agent_name=None`): delegates to `WorkspaceSupervisor`, returns `WorkspaceChatView(response, conversation_id, agent_used)`.
  - **Agent-direct path** (`agent_name` set): resolves an LLM override from the registry if `provider`/`model` are given, then delegates to `ConversationService.get_or_create_clone()`. Raises `ServiceValidationError` if `provider`/`model` are set without `agent_name`, or if `conversation_id` is not a valid UUID.
- `stream_chat(...)` — agent-direct path only; returns `(AsyncIterator[str], conversation_id_str, agent_name)`. Raises `ServiceValidationError` if `agent_name` is absent (supervisor streaming is a future enhancement).
- `update_workspace()` mutates the config in-place (safe because no structural rebuild is needed).

**`ConversationPool`** — application-scoped LRU cache of per-conversation agent clones, keyed by `(workspace_name, agent_name, conversation_id)`. Evicts the least-recently-used entry when the pool is full. Supports TTL-based bulk expiry. Never touches the DB — purely in-memory.

**`ConversationService`** — manages the clone lifecycle for individual conversations via `get_or_create_clone(workspace, agent, conversation_id, session, *, llm_override=None)`:
- **Pool hit:** returns the existing clone immediately (skipped when `llm_override` is set).
- **New conversation:** clones the template agent, optionally persists a new `Conversation` row, stores the clone in the pool.
- **Cold-start** (known `conversation_id`, pool miss): validates the conversation exists in the DB, then clones the template and binds the `conversation_id` for lazy history reload.
- **LLM override path:** when `llm_override` is set, creates an ephemeral clone with the given LLM, still creates a DB row if a session is available, but does **not** store the clone in the pool. This makes model-overridden requests stateless per-turn.

**Request DTOs** — Pydantic v2 request models for create/update/chat operations.

**View dataclasses** — frozen response projections (`AgentView`, `WorkspaceView`, `WorkspaceDetailView`, `WorkspaceChatView`, `ConversationView`, `ProviderView`, `ProviderModelsView`). No logic — pure data for serialisation.

**Typed domain exceptions:**

| Exception | HTTP mapping | Attributes |
|---|---|---|
| `NotFoundError` | 404 | `kind`, `name` |
| `AlreadyExistsError` | 409 | `kind`, `name` |
| `ServiceValidationError` | 422 | `message` |

---

### API

**Bootstrap (lifespan):**
1. Call `build_registry()` (from `personal_assistant/bootstrap.py`) to create the provider registry with `AnthropicProvider` and `OllamaProvider` (default).
2. Create the orchestrator, store on application state.
3. Call the workspace factory, add the default workspace to the orchestrator.
4. If `DATABASE_URL` is set: build the async engine + session factory, store on application state.
5. On shutdown: dispose the engine if present.

**Dependency injection** — request-scoped:
- Orchestrator — retrieved from application state (no allocation per request).
- `ProviderRegistry` — retrieved from the orchestrator on application state.
- `WorkspaceService` / `AgentService` — constructed fresh per request (stateless wrappers). `WorkspaceService` is injected with a `ConversationService` to support agent-direct chat.
- `AsyncSession | None` — yielded from the session factory if one is configured; `None` otherwise (graceful no-DB degradation).

**Routers:**
- `/workspaces` — workspace CRUD + workspace-level chat (supervisor or agent-direct) + streaming.
- `/workspaces/{workspace_name}/agents` — agent CRUD + per-agent chat (non-streaming and SSE streaming) + reset.
- `/providers` — provider discovery: list providers, list models for a provider.

**Exception handlers** — map service exceptions to HTTP responses with a structured `ErrorResponse(error, detail)` body. A catch-all `Exception` handler returns `{"error": "internal_server_error"}` with 500 and logs the traceback server-side, preventing stack traces from leaking to clients.

**Response DTOs** — Pydantic models with `from_view()` factory methods that consume service-layer view dataclasses. Separate from service schemas to keep serialisation and OpenAPI docs out of the service layer.

---

### Persistence (optional)

**Engine + session factory** — two factory functions with no global state. The session factory is stored on application state and injected per-request via DI.

**ORM models:**
- `Conversation` — `agent_name`, `workspace_name` (denormalised strings), `created_at`, `updated_at`.
- `Message` — `role` (`"human"` | `"ai"`), text content, optional `JSONB extra_metadata`.

**Repository** — explicit-transaction async data-access layer. Instantiated inline when a session is available; never referenced from core domain logic directly.

---

## Key Design Decisions

### Lazy graph rebuild (`_dirty` flag)
LangGraph compiles a graph from the LLM and tool list. Recompiling on every `register_tool` call would be expensive. Instead, the flag is set on any tool change and the graph is (re)built only at the next inference call. A `batch_tools()` context manager makes bulk tool operations a single rebuild.

### Lazy history loading
Setting `conversation_id` to resume a conversation is a cheap assignment. The DB round-trip to load history happens only on the first `run()` / `stream()` call that actually needs it, gated by `_history_loaded`. This avoids unnecessary queries when introspecting an agent without running it.

### Tool config-injection via `model_copy()`
Tools that declare an `agent_config` field receive an agent-specific copy at registration time. The shared tool instance is never mutated, so the same tool object can be registered with multiple agents and each gets its own bound instance. This allows tools to introspect their owning agent without creating bidirectional coupling.

### Bidirectional tool propagation in `Workspace`
The workspace is the unit of tool coordination. When a tool is added to a workspace it is propagated to all current agents; when an agent joins a workspace it receives all current tools. Agents never need direct references to each other, and tool lifecycle is managed in one place.

### Supervisor-based workspace routing
Rather than requiring callers to name a specific agent for workspace-level chat, the workspace owns a `WorkspaceSupervisor` that uses a separate LLM call to route each turn to the most suitable agent based on agent descriptions and conversation history. This decouples routing policy from the caller. The supervisor is rebuilt automatically whenever the agent roster changes.

### Conversation threading via `conversation_id`
All workspace chat endpoints expose a single `conversation_id: str` field. For the supervisor path this maps to the LangGraph `MemorySaver` checkpointer's internal `thread_id` string; for the agent-direct path it maps to the `uuid.UUID` used by `ConversationPool` and the persistence layer (converted at service boundary). Callers receive `conversation_id` in every response and pass it back on subsequent turns. A new identifier is generated for new conversations. This makes conversation continuity explicit and stateless from the API caller's perspective — the server holds the state, the client holds the key.

### Per-conversation agent clones via `ConversationPool`
For direct (non-supervisor) agent chat, each conversation gets its own agent clone rather than sharing a single agent instance. The pool manages clone lifecycle with LRU eviction and TTL expiry. This isolates conversation history between concurrent users while keeping memory bounded.

### Optional persistence — additive, not intrusive
The `AsyncSession | None` pattern throughout the call path means the entire system works with `None`. No core logic is conditional on persistence availability except for explicit `if session:` guards. The system runs fully in-memory without any database configuration.

### Request-scoped services
`AgentService` and `WorkspaceService` are constructed fresh per request. The orchestrator on application state is the only application-scoped mutable state. Services are stateless wrappers; there is no shared mutable state between requests, so no locking is needed at the service level.

### View + Response DTO split
- **Service views** — plain frozen dataclasses, easy to construct in tests, carry no serialisation logic.
- **API response schemas** — handle Pydantic serialisation and OpenAPI doc generation via `from_view()` factory methods.

This keeps the service layer fully decoupled from FastAPI/Pydantic response concerns.

### SSE streaming with plain-text tokens + `[DONE]` sentinel
Streaming responses emit `data: {token}\n\n` lines and terminate with `data: [DONE]\n\n`. Using raw text tokens (not JSON-wrapped objects) keeps client parsing trivial. The agent existence check runs before the generator starts so that 404 errors are returned as proper HTTP responses, not embedded in the event stream.

### Agent update resets conversation history
Updating an agent replaces it entirely. There is no "soft update" path — agent config changes (system prompt, model, allowed tools) may require a new LangGraph graph, and the simplest correct approach is a full rebuild. Clients that need stateful conversations should not update agents mid-conversation.

---

## Data Flow Diagrams

### 1. Startup Bootstrap

```
App lifespan start
  │
  ├─ ProviderRegistry()
  │    ├─ register(AnthropicProvider())
  │    └─ register(OllamaProvider())  ← set as default
  │
  ├─ Orchestrator(registry)  →  app state
  │
  ├─ workspace factory
  │    └─ WorkspaceConfig → Workspace
  │         └─ AgentConfig → Agent.from_config(registry)
  │              └─ registry.get(provider) → AIProvider.get_model(model) → BaseChatModel
  │
  └─ if DATABASE_URL:
       ├─ build_engine(url)  →  AsyncEngine
       ├─ build_session_factory(engine)  →  async_sessionmaker
       └─ app state ← session_factory
```

### 2. Non-Streaming Agent Chat

```
POST /workspaces/{workspace_name}/agents/{agent_name}/chat
  { "message": "Hello" }
  │
  ├─ Pydantic validates body → ChatRequest
  ├─ DI: AgentService(orchestrator)
  ├─ DI: AsyncSession | None
  │
  └─ AgentService.run_agent(workspace_name, agent_name, message, session)
       ├─ validate workspace + agent exist  (NotFoundError on miss)
       └─ agent.run(message, session)
            ├─ _ensure_graph()      ← rebuild LangGraph if dirty
            ├─ _ensure_history_loaded(session)  ← DB fetch if session + not loaded
            ├─ append HumanMessage to history
            ├─ graph.ainvoke({"messages": history})
            │    └─ ReAct loop:
            │         LLM call → [tool calls?] → tool execution → LLM call → AIMessage
            ├─ update history with result messages
            └─ return last message content (str)
  │
  └─ ChatResponse(reply=response)
```

### 3. Streaming Agent Chat

```
POST /workspaces/{workspace_name}/agents/{agent_name}/chat/stream
  { "message": "Hello" }
  │
  ├─ validate agent exists  ← NotFoundError → 404 before headers are sent
  │
  └─ StreamingResponse(generate(), media_type="text/event-stream")
       └─ generate():
            └─ agent.stream(message, session)
                 ├─ _ensure_graph()
                 ├─ _ensure_history_loaded(session)
                 ├─ append HumanMessage
                 ├─ graph.astream({"messages": history})
                 │    └─ for each token chunk:
                 │         yield  "data: {token}\n\n"
                 └─ yield  "data: [DONE]\n\n"
```

### 4. Workspace-Level Chat — Supervisor Path

```
POST /workspaces/{workspace_name}/chat
  { "message": "Help me with my CV", "conversation_id": null }
  │
  ├─ Pydantic validates body → WorkspaceChatRequest
  ├─ DI: WorkspaceService(orchestrator, conversation_service)
  │
  └─ WorkspaceService.chat(workspace_name, message, conversation_id=None, agent_name=None, ...)
       ├─ validate workspace exists  (NotFoundError on miss)
       └─ orchestrator.delegate_to_workspace(message, workspace_name, thread_id=None)
            └─ WorkspaceSupervisor.run(message, thread_id)
                 ├─ generate new thread_id if none provided
                 ├─ graph.ainvoke({"messages": [HumanMessage]}, config={"thread_id": ...})
                 │    ├─ supervisor node:
                 │    │    ├─ LLM inspects agent descriptions + conversation
                 │    │    └─ emits structured routing decision → agent name
                 │    └─ agent node (e.g. CareerAgent):
                 │         ├─ agent.run_with_context(messages)
                 │         └─ Command(goto="supervisor", update={"messages": [AIMessage]})
                 │    └─ supervisor node sees AIMessage → Command(goto=END)
                 └─ return (response_text, thread_id, agent_used)
  │
  └─ WorkspaceChatResponse(response=..., conversation_id=..., agent_used=...)
```

### 5. Workspace-Level Chat — Agent-Direct Path (with optional model override)

```
POST /workspaces/{workspace_name}/chat
  { "message": "Hello", "agent_name": "Assistant",
    "provider": "anthropic", "model": "claude-haiku-4-5-20251001" }   ← optional override
  │
  └─ WorkspaceService.chat(..., agent_name="Assistant", provider="anthropic", model="...")
       ├─ validate provider/model not set without agent_name  (ServiceValidationError)
       ├─ validate workspace exists
       ├─ resolve override_llm from registry if provider/model set
       └─ ConversationService.get_or_create_clone(ws, agent, conv_uuid, session, llm_override=...)
            ├─ llm_override set → ephemeral clone (not pooled), create DB row if session
            └─ return (clone, conversation_id)
       └─ clone.run(message, session)
  │
  └─ WorkspaceChatResponse(response=..., conversation_id=..., agent_used="Assistant")
```

---

## Endpoint Reference

| Method | Path | Description | Status |
|---|---|---|---|
| `GET` | `/health` | Health check | 200 |
| `GET` | `/providers/` | List all registered providers | 200 |
| `GET` | `/providers/{name}/models` | List available models for a provider | 200 |
| `POST` | `/workspaces` | Create a workspace | 201 |
| `GET` | `/workspaces` | List all workspaces | 200 |
| `GET` | `/workspaces/{workspace_name}` | Get workspace details | 200 |
| `PATCH` | `/workspaces/{workspace_name}` | Update workspace metadata | 200 |
| `DELETE` | `/workspaces/{workspace_name}` | Delete a workspace | 204 |
| `POST` | `/workspaces/{workspace_name}/chat` | Workspace chat — supervisor or agent-direct (supports `agent_name`, `provider`, `model`, `conversation_id`) | 200 |
| `POST` | `/workspaces/{workspace_name}/chat/stream` | Streaming workspace chat — agent-direct only (SSE, requires `agent_name`) | 200 |
| `POST` | `/workspaces/{workspace_name}/agents` | Create an agent | 201 |
| `GET` | `/workspaces/{workspace_name}/agents` | List agents in workspace | 200 |
| `GET` | `/workspaces/{workspace_name}/agents/{agent_name}` | Get agent details | 200 |
| `PATCH` | `/workspaces/{workspace_name}/agents/{agent_name}` | Update agent config | 200 |
| `DELETE` | `/workspaces/{workspace_name}/agents/{agent_name}` | Delete an agent | 204 |
| `POST` | `/workspaces/{workspace_name}/agents/{agent_name}/chat` | Non-streaming agent chat | 200 |
| `POST` | `/workspaces/{workspace_name}/agents/{agent_name}/chat/stream` | Streaming agent chat (SSE) | 200 |
| `POST` | `/workspaces/{workspace_name}/agents/{agent_name}/reset` | Reset conversation history | 204 |
| `GET` | `/workspaces/{workspace_name}/agents/{agent_name}/conversations` | List conversations (requires DB) | 200 |
| `DELETE` | `/workspaces/{workspace_name}/agents/{agent_name}/conversations/{id}` | Delete a conversation (requires DB) | 204 |

---

## Extension Guide

### Add a new AI provider

1. Subclass `AIProvider` and `ProviderConfig` in the providers package:
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

       async def list_models(self) -> list[str]:   # optional override
           return ["my-model", "my-model-large"]
   ```
2. Register in the app bootstrap:
   ```python
   registry.register(MyProvider())
   ```

### Add a new tool

1. Subclass `AssistantTool` in the tools package:
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
2. Add to a workspace: `workspace.add_tool(MyTool())`.

   To give the tool access to its owning agent, add `agent_config: AgentConfig | None = None` to the input schema — the agent injects a bound copy automatically at registration time.

### Add a new agent

Use `AgentConfig` directly or subclass `Agent`:

```python
from personal_assistant.core.agent import AgentConfig
from personal_assistant.services.agent_service import AgentService

config = AgentConfig(
    name="my_agent",
    description="Specialist agent.",  # used by the supervisor for routing
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

1. Create a factory function in the workspaces package:
   ```python
   from personal_assistant.core.orchestrator import Orchestrator
   from personal_assistant.core.workspace import Workspace, WorkspaceConfig

   def create_my_workspace(orchestrator: Orchestrator) -> Workspace:
       ws = Workspace(WorkspaceConfig(name="my_workspace", description="..."))
       # add agents and tools
       orchestrator.add_workspace(ws)
       return ws
   ```
2. Call the factory in the app bootstrap lifespan after the orchestrator is created.

### Add a new API endpoint

1. Add the route to the appropriate router:
   ```python
   @router.post("/{agent_name}/my_action", status_code=200)
   async def my_action(
       workspace_name: WorkspaceName,
       agent_name: AgentName,
       service: AgentService = Depends(get_agent_service),
   ) -> MyResponse:
       result = await service.my_operation(workspace_name, agent_name)
       return MyResponse.from_view(result)
   ```
2. Add the corresponding method to `AgentService` or `WorkspaceService`.
3. If a new exception type is introduced, register a handler in the exception handlers module.
