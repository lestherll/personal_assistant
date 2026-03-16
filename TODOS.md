# TODOS

Prioritised backlog from the 2026-03-16 product expansion review.
Items are grouped by theme and ordered P0 → P3 within each group.

---

## Critical fixes (P0)

### Stream error sentinel
**What:** Wrap `_generate()` in `AgentService.stream_agent` with a `try/except` that emits `data: [ERROR]\n\n` on failure before the generator exits.
**Why:** Any exception mid-stream (timeout, provider 500, tool crash) currently produces a truncated SSE response with no `[DONE]`. Clients cannot distinguish a clean finish from a crash — they hang waiting for a sentinel that never arrives. Conversation history write is also skipped, losing the partial turn.
**Where:** `personal_assistant/services/agent_service.py` → `stream_agent._generate()`
**Effort:** S | **Priority:** P0

### LLM retry on transient errors
**What:** Wrap the resolved LLM in `personal_assistant/core/agent.py` with `llm.with_retry(stop_after_attempt=3)` to handle provider 429s and transient 5xxs.
**Why:** Provider errors are transient — a single retry after 1-2 seconds succeeds the vast majority of the time. Right now any LLM-level error immediately returns a 500 to the user.
**Where:** `personal_assistant/core/agent.py` → wherever `get_model()` result is stored on the agent
**Effort:** S | **Priority:** P0

---

## Security & correctness (P1)

### Fix `allowed_tools` semantics
**What:** Change the meaning of `allowed_tools` so that `None`/`null` = all tools allowed, `[]` = no tools, `["tool_a"]` = explicit allowlist. Requires one Alembic migration to convert existing empty-array rows to `NULL`.
**Why:** The current `[] = all tools` semantic is a hidden footgun — an empty list intuitively means "none", not "everything". As the tool management system is built, `allowed_tools` becomes a real security boundary, not just a config hint. Fixing the semantics now prevents a breaking change later.
**Where:** `personal_assistant/persistence/models.py`, `personal_assistant/services/agent_service.py` (`_row_to_view`), new Alembic migration
**Effort:** S | **Priority:** P1

### API key system
**What:** Long-lived, revocable API keys (`sk-...` style) as an alternative to JWT for programmatic access. New `UserAPIKey` DB table with hashed key, name, created/last-used timestamps, optional expiry. Endpoints: `POST /auth/api-keys`, `GET /auth/api-keys`, `DELETE /auth/api-keys/{id}`. Auth middleware checks `Authorization: Bearer` for both JWT and API key (raw key hashed on each request, compared against stored hash).
**Why:** JWT is right for browser sessions but painful for scripts and integrations — tokens expire, refresh flows are awkward, you can't put a JWT in a `.env` file. API keys are what developers expect.
**Where:** New `persistence/models.py` table, `auth/tokens.py` or new `auth/api_keys.py`, `api/dependencies.py` (`get_current_user`), `api/routers/auth.py`
**Effort:** M | **Priority:** P1

### Per-user rate limiting on chat endpoints
**What:** Middleware that enforces a per-user request-per-minute cap on the chat endpoints (`/agents/{a}/chat`, `/agents/{a}/chat/stream`, `/workspaces/{w}/chat`, `/workspaces/{w}/chat/stream`). Returns HTTP 429 with `Retry-After` header when the limit is exceeded.
**Why:** LLM calls are expensive. An unthrottled user can run up unbounded API costs and degrade response times for everyone. A simple sliding-window limiter prevents worst-case abuse.
**Where:** `api/main.py` (middleware registration), new `api/middleware/rate_limit.py`. Start with in-memory (single-process); replace with Redis when cache is upgraded.
**Effort:** M | **Priority:** P1

### Concurrent chat race condition
**What:** Two simultaneous requests using the same `conversation_id` both load history at `t=0`, both append their messages, and the last writer wins — silently discarding the first turn from history. Fix with a per-`conversation_id` `asyncio.Lock` in `AgentService`.
**Why:** Happens on double-submit, client retry of a slow request, or any client that doesn't wait for a response before sending the next message. The corrupted history is invisible — the agent simply won't remember the dropped turn.
**Where:** `personal_assistant/services/agent_service.py` → `_prepare_agent` / `run_agent` / `stream_agent`. In-memory lock is sufficient for single-process; replace with Redis lock when the cache is upgraded.
**Effort:** M | **Priority:** P2 (P1 once multi-user load increases)

---

## API completeness (P1–P2)

### Cross-workspace conversation list
**What:** `GET /workspaces/{workspace_name}/conversations` — list all conversations in a workspace across all agents, not just per-agent.
**Why:** The `Conversation` model is scoped to `workspace_id`, not `agent_id`. The data already supports a unified view. Without this endpoint, a chat UI sidebar cannot show a complete conversation history — it would have to query every agent separately.
**Where:** `api/routers/workspaces.py`, `personal_assistant/services/agent_service.py` (or new `WorkspaceService` method), `personal_assistant/persistence/repository.py`
**Effort:** S | **Priority:** P1

### Conversation message history endpoint
**What:** `GET /workspaces/{workspace_name}/conversations/{conversation_id}/messages` — retrieve the messages of a past conversation.
**Why:** Conversation history is currently write-only from the API's perspective. The agent uses it internally but no client can display a conversation replay. For any chat UI, this is essential: users need to re-open a past conversation and see what was said.
**Where:** `api/routers/workspaces.py`, `personal_assistant/services/agent_service.py`, `personal_assistant/persistence/repository.py`
**Effort:** S | **Priority:** P1

### Provider health check endpoint
**What:** `GET /providers/{name}/health` — a liveness check for a registered provider. For Ollama: hits `/api/tags` (already used in `list_models()`). For Anthropic: a minimal API call. Returns `{"status": "ok"}` or `{"status": "error", "detail": "..."}`.
**Why:** The most common debugging question is "why isn't my agent responding?" — is it the app or the provider? This endpoint answers it immediately. Also enables a meaningful docker-compose `healthcheck`.
**Where:** `personal_assistant/providers/base.py` (new `health()` abstract method), `providers/anthropic.py`, `providers/ollama.py`, `api/routers/providers.py`
**Effort:** S | **Priority:** P1

### Pagination on list endpoints
**What:** Add `skip: int = 0, limit: int = 50` query parameters to `list_conversations`, `list_agents`, `list_workspaces`, and the new cross-workspace conversation list. Apply `.offset(skip).limit(limit)` in the repository queries.
**Why:** All list endpoints currently return unbounded results. A user with 500 conversations gets all 500 in one response. At scale this causes slow queries, large payloads, and client-side rendering issues.
**Where:** All `list_*` methods in `persistence/repository.py` and `persistence/user_workspace_repository.py`, corresponding service methods, API router query params
**Effort:** S | **Priority:** P2

### Usage analytics endpoints
**What:** `GET /usage/summary` and `GET /usage/by-agent` — aggregate token counts and estimated cost grouped by workspace, agent, provider, and time period. The raw data already exists in `Message.prompt_tokens` / `Message.completion_tokens` / `Message.provider` / `Message.model`.
**Why:** Users have no visibility into how much they're using the system or which agents are most active. The data is already being collected (migration 0008) but never surfaced.
**Where:** New `api/routers/usage.py`, new `services/usage_service.py`, SQL aggregates on the `messages` table
**Effort:** M | **Priority:** P2

---

## Product features (P2)

### LLM-generated conversation titles
**What:** After the first AI response in a new conversation, fire a background LLM call to generate a 5-7 word title and save it to a new `title` column on the `Conversation` model. Requires one Alembic migration. Title generation failure must be non-fatal — the chat response is already delivered before this runs.
**Why:** Every conversation is currently identified only by UUID. A chat UI sidebar is unusable without titles. Auto-generation means zero friction — titles appear without the user doing anything.
**Where:** New Alembic migration, `persistence/models.py` (`Conversation.title`), `services/agent_service.py` (`run_agent` / `stream_agent` — trigger after turn 1), new lightweight title-generation helper
**Effort:** M | **Priority:** P2

### Workspace template system
**What:** DB-seeded workspace templates browsable via `GET /templates/` and installable via `POST /templates/{id}/install`. Installing a template creates a new `UserWorkspace` and `UserAgent` rows from the template's agent definitions, analogous to `fork_default_workspace` in `AuthService`. New DB tables: `workspace_templates` and `template_agents`.
**Why:** The only "template" today is the hardcoded default workspace in `workspaces/default_workspace.py`. There is no way to browse, install, or share workspace configurations. This is the foundation of the "agent gallery" vision — pre-built configurations like "Job Hunt Workspace", "Full-Stack Coding Assistant", "Legal Research Stack".
**Where:** New Alembic migrations, `persistence/models.py`, new `services/template_service.py`, `api/routers/templates.py`, seed data script
**Effort:** L | **Priority:** P2

### Full tool management system
**What:** Tools as first-class DB rows with name, description, version, schema, and enabled status. New DB table `tools`. `GET /tools/` exposes the registry to API clients. Tools can be attached/detached per workspace or agent. Tool discovery is required before building any UI agent editor.
**Why:** Tools are currently globally registered in Python code — invisible to the API, impossible to manage without redeploying. The tool registry is an `AgentService` constructor argument that clients can't inspect. As the tool ecosystem grows (more tools, per-user tools, third-party plugins), the tool system needs to be a first-class API concern.
**Where:** New Alembic migration, `persistence/models.py`, new `services/tool_service.py`, `api/routers/tools.py`, update `AgentService` to resolve tools from DB
**Effort:** L | **Priority:** P2

---

## Infrastructure (P1)

### Dockerfile + docker-compose
**What:** A production-grade `Dockerfile` (uv sync, alembic upgrade head as init step, uvicorn) and `docker-compose.yml` (app + postgres + optional redis). `HEALTHCHECK` instruction in Dockerfile. Graceful shutdown via SIGTERM in FastAPI lifespan hook.
**Why:** Anyone who wants to run this today needs Python 3.13, uv, and a Postgres instance configured manually. Docker makes this a single `docker compose up`. It also unblocks deployment to any Docker host (Fly.io, Railway, Render, self-hosted).
**Where:** New `Dockerfile`, `docker-compose.yml`, update `.env.example` with compose-compatible defaults
**Effort:** M | **Priority:** P1

---

## Quality of life (P2–P3)

### Workspace clone endpoint
**What:** `POST /workspaces/{name}/clone` — duplicates a workspace's agent configurations into a new workspace (no conversation history). Lets users create variants of a working setup without manual recreation.
**Why:** Experimenting with agent configurations requires recreating the entire workspace from scratch. Clone makes iteration fast. This is a small addition once the template install pattern exists (clone is essentially "install from self").
**Where:** `api/routers/workspaces.py`, `services/workspace_service.py`
**Effort:** S | **Priority:** P2

### Agent routing transparency
**What:** Add `routing_reason: str | None` to the `WorkspaceChatResponse` schema. The supervisor's `route()` call already receives a structured LLM response — the reason string is currently discarded. Surfacing it lets users understand and debug routing decisions.
**Why:** When the supervisor routes a message to the wrong agent, there is currently no way to see why. A `routing_reason` field (e.g. "Routed to coding_agent: message contains Python debugging request") lets users tune agent descriptions and builds trust in the supervisor.
**Where:** `personal_assistant/core/supervisor.py` (`route()` return type), `services/workspace_service.py`, `services/views.py`, `api/schemas.py`
**Effort:** S | **Priority:** P3

---

## Roadmap (previously documented)

- **Supervisor streaming** — LangGraph graph-level streaming for workspace chat without requiring `agent_name`. Blocked by LangGraph supervisor graph streaming support.
- **Redis-backed conversation cache** — drop-in replacement for `InMemoryConversationCache`. Unblocks multi-process deployment and the concurrent chat race condition fix.
- **More providers** — OpenAI, Groq, Google Gemini. Each is a `AIProvider` subclass + entry in `build_registry()`.
- **Web UI** — chat interface, workspace composer, template gallery. Build after API hardening is complete.
