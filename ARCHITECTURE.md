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
│  AgentService · WorkspaceService · AuthService           │
│  ConversationCache · Views · Exceptions                  │
├──────────────────────────────────────────────────────────┤
│  Core Domain                        Provider Registry    │
│  Orchestrator · Workspace ·         ProviderRegistry ·   │
│  WorkspaceSupervisor · Agent ·      AIProvider           │
│  AssistantTool                                           │
├──────────────────────────────────────────────────────────┤
│  Persistence (optional)                                  │
│  SQLAlchemy · Repositories · ORM Models                  │
└──────────────────────────────────────────────────────────┘
```

Each tier depends only on the tier directly below it. The API never touches the core domain directly — it always goes through the service layer.

---

## Layer Responsibilities

| Layer | Owns | Does not own |
|---|---|---|
| **API** | HTTP routing, request/response serialisation, DI wiring, HTTP error mapping | Business logic, domain state |
| **Service** | CRUD semantics, typed domain exceptions, domain-to-view projection, conversation lifecycle | HTTP concerns, persistence details |
| **Core** | Agent lifecycle, workspace coordination, supervisor routing, LLM orchestration, tool management | HTTP, serialisation, DB queries |
| **Providers** | LLM construction, provider-specific config | Agent state, tool registration |
| **Persistence** | DB schema, session management, message storage | Domain logic, agent lifecycle |

---

## Core Concepts

### Provider Registry

A named dictionary of AI provider instances with a default pointer. Each provider wraps a LangChain chat model and exposes two operations: construct a model instance (with optional model override), and list available models. The default `list_models` implementation returns the provider's default model; concrete providers override it to expose their full catalogue. The first registered provider becomes the default unless overridden.

Providers are registered once at bootstrap and shared across the entire application. Adding a new provider means subclassing the abstract base and registering it in the bootstrap.

### Agents

An agent combines an LLM (resolved from the provider registry), a system prompt, a set of allowed tools, and a conversation history. It runs a LangGraph ReAct loop: the LLM reasons, optionally calls tools, receives results, and iterates until it produces a final answer.

Key behaviours:
- **Lazy graph rebuild** — the LangGraph compiled graph is rebuilt only at the next inference call after any tool change, not on every mutation.
- **Lazy history loading** — when resuming a conversation, history is loaded from the DB on the first inference call, not at construction time.
- **Cloning** — a fresh agent with the same config and tools but empty history can be produced for per-conversation isolation or ephemeral model overrides.

### Tools

Tools are typed, validated LangChain-compatible units of capability. Each tool declares a name, description (shown to the LLM), a Pydantic input schema, and a synchronous `_run` implementation. Tools that declare an `agent_config` field receive an agent-specific copy at registration time via `model_copy`, so the same tool can be registered with multiple agents without shared mutable state.

### Workspaces

A workspace is a named container for agents and tools. Tool propagation is bidirectional: adding a tool to a workspace registers it with all existing agents; adding an agent to a workspace gives it all existing workspace tools. Agent-private tools can be registered directly to a single agent without propagating to others.

Each workspace owns a supervisor that routes workspace-level chat to the most suitable agent. The supervisor is rebuilt automatically whenever the agent roster changes.

### Supervisor

The supervisor provides two routing facilities:

1. **Lightweight routing** — a single-shot structured LLM call that returns the name of the best agent for a given message. Used by the service layer for API requests.
2. **Full graph routing** — a LangGraph `StateGraph` with a supervisor node and one node per agent, backed by `MemorySaver` for conversation threading across turns. Used in the REPL and core layer.

Both facilities fall back to the first available agent if the routing decision is invalid.

### Services

Services are stateless singletons that sit between the API layer and the core domain. They translate between HTTP request/response shapes (Pydantic schemas) and domain objects, enforce business rules, manage conversation lifecycle, and raise typed domain exceptions that the API layer maps to HTTP status codes.

- **AgentService** — CRUD over agent configs, chat (streaming and non-streaming), conversation history management. Builds ephemeral agent instances per request, restores history from cache (or DB on miss), and writes updated history back to cache.
- **WorkspaceService** — CRUD over workspace configs, workspace-level chat with two routing modes: supervisor (auto-routing) or agent-direct (skip supervisor).
- **AuthService** — user registration, login, token refresh. Stateless JWT auth (Argon2 password hashing, HS256 tokens).

### Conversation Cache

An abstract pluggable LRU cache for conversation message histories, keyed by `(user_id, workspace_name, conversation_id)`. The built-in implementation is in-memory (backed by `collections.OrderedDict`). Future backends (e.g. Redis) can be added by subclassing the abstract base.

### Persistence

Optional PostgreSQL-backed persistence via async SQLAlchemy. ORM models cover users, workspaces, agents, conversations, and messages. The `AsyncSession | None` pattern throughout the call path means the entire system works without a database — no core logic is conditional on persistence availability except for explicit `if session:` guards.

---

## Key Design Decisions

### Lazy graph rebuild
LangGraph compiles a graph from the LLM and tool list. Recompiling on every tool registration would be expensive. Instead, a dirty flag is set on any tool change and the graph is rebuilt only at the next inference call. A `batch_tools()` context manager makes bulk tool operations trigger a single rebuild.

### Lazy history loading
Setting a `conversation_id` to resume a conversation is a cheap assignment. The DB round-trip to load history happens only on the first `run()` / `stream()` call, avoiding unnecessary queries when introspecting an agent without running it.

### Tool config-injection via model copy
Tools that declare an `agent_config` field receive an agent-specific copy at registration time. The shared tool instance is never mutated, so the same tool object can be registered with multiple agents and each gets its own bound instance.

### Bidirectional tool propagation
The workspace is the unit of tool coordination. Adding a tool propagates it to all current agents; adding an agent gives it all current workspace tools. Tool lifecycle is managed in one place without agents needing direct references to each other.

### Supervisor-based workspace routing
Rather than requiring callers to name a specific agent, the workspace supervisor uses a separate LLM call to route each turn to the most suitable agent based on agent descriptions. This decouples routing policy from the caller and from individual agent implementations.

### Conversation threading via conversation_id
All chat endpoints expose a single `conversation_id` field. Callers receive it in every response and pass it back on subsequent turns. A new identifier is generated for new conversations. This makes conversation continuity explicit and stateless from the API caller's perspective — the server holds the state, the client holds the key.

### Optional persistence — additive, not intrusive
The system runs fully in-memory without any database configuration. Persistence is additive: conversation and message history are stored when a DB session is available, and gracefully omitted when it is not.

### View + Response DTO split
Service views are plain frozen dataclasses — easy to construct in tests, no serialisation logic. API response schemas handle Pydantic serialisation and OpenAPI doc generation via factory methods that consume service views. This keeps the service layer fully decoupled from FastAPI/Pydantic response concerns.

### SSE streaming
Streaming responses emit `data: {token}\n\n` lines and terminate with `data: [DONE]\n\n`. Using raw text tokens (not JSON-wrapped objects) keeps client parsing trivial. Agent existence is validated before the generator starts, so 404 errors are returned as proper HTTP responses, not embedded in the event stream.

---

## Data Flow

### Startup

1. Build the provider registry (register Anthropic and Ollama providers).
2. Create the orchestrator with the registry.
3. Run workspace factories to populate the default workspace with agents and tools.
4. If `DATABASE_URL` is set: build the async engine and session factory, store on application state.
5. Instantiate `AgentService` and `WorkspaceService` as singletons on application state.

### Non-Streaming Agent Chat

```
POST /workspaces/{workspace}/agents/{agent}/chat
  │
  ├─ Validate body → resolve agent from DB
  ├─ Restore conversation history (cache → DB on miss)
  ├─ Build ephemeral Agent instance
  ├─ agent.run(message)
  │    ├─ LLM call → [tool calls?] → tool execution → LLM call → AIMessage
  │    └─ ReAct loop until final answer
  ├─ Write updated history to cache
  └─ Return { reply, conversation_id }
```

### Workspace Chat — Supervisor Path

```
POST /workspaces/{workspace}/chat  (no agent_name)
  │
  ├─ Load workspace agents from DB
  ├─ route(message, agents, llm) → agent_name   ← single LLM call
  └─ Delegate to AgentService.run_agent(agent_name, ...)
```

### Workspace Chat — Agent-Direct Path

```
POST /workspaces/{workspace}/chat  (agent_name set)
  │
  ├─ Optionally resolve LLM override from registry (provider + model)
  └─ Delegate to AgentService.run_agent(agent_name, ..., llm_override)
```

### Streaming

Streaming follows the same path as non-streaming, but `agent.stream(message)` is called instead, yielding tokens as `data: {token}\n\n` SSE events, terminated by `data: [DONE]\n\n`.
