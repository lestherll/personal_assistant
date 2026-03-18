# TODOS

Prioritised backlog from the 2026-03-16 product expansion review.
Items are grouped by theme and ordered P0 → P3 within each group.

---

## Critical fixes (P0) — DONE

### ~~Stream error sentinel~~ ✓
Implemented: SSE helper in `api/streaming.py` with `[DONE]`/`[ERROR]` sentinels + service-layer error handling in `_generate()`.

### ~~LLM retry on transient errors~~ ✓
Implemented: `ModelRetryMiddleware` passed via `middleware` param to `create_agent()` in `Agent._build_graph()`.

---

## Security & correctness (P1) — DONE

### ~~Fix `allowed_tools` semantics~~ ✓
Implemented: `None` = all tools, `[]` = no tools, explicit list = allowlist. Alembic migration 0009.

### ~~API key system~~ ✓
Implemented: `UserAPIKey` model, SHA-256 hashing, `sk-` prefix detection in `get_current_user`, CRUD endpoints at `/auth/api-keys`.

### ~~Per-user rate limiting on chat endpoints~~ ✓
Implemented: Fixed-window `RateLimiter` as FastAPI dependency on all chat endpoints.

### ~~Concurrent chat race condition~~ ✓
Implemented: Per-conversation `asyncio.Lock` in `AgentService` with bounded LRU eviction.

---

## API completeness (P1–P2)

### ~~Cross-workspace conversation list~~ ✓
Already built at `GET /workspaces/{name}/conversations`.

### ~~Conversation message history endpoint~~ ✓
Implemented: `GET /workspaces/{name}/conversations/{conversation_id}/messages`.

### ~~Provider health check endpoint~~ ✓
Implemented: `GET /providers/{name}/health` with Ollama-specific `/api/tags` check.

### ~~Pagination on list endpoints~~ ✓
Implemented: `skip`/`limit` query params added to list endpoints with repository `.offset().limit()` and tests covering unit and functional pagination.

### Usage analytics endpoints
**What:** `GET /usage/summary` and `GET /usage/by-agent` — aggregate token counts and estimated cost grouped by workspace, agent, provider, and time period. The raw data already exists in `Message.prompt_tokens` / `Message.completion_tokens` / `Message.provider` / `Message.model`.
**Why:** Users have no visibility into how much they're using the system or which agents are most active. The data is already being collected (migration 0008) but never surfaced.
**Where:** New `api/routers/usage.py`, new `services/usage_service.py`, SQL aggregates on the `messages` table
**Effort:** M | **Priority:** P2

---

## Product features (P2)

### ~~LLM-generated conversation titles~~ ✓
Implemented: Alembic migration `0010_add_conversation_title.py`; `Conversation.title` storage + API/view exposure; first-turn auto-title generation in `AgentService.run_agent()` and `stream_agent()`; manual rename endpoint at `PATCH /workspaces/{name}/conversations/{conversation_id}` with ownership checks and DB-session validation.

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

### API key rotation / re-generation
**What:** `POST /auth/api-keys/{id}/rotate` — revoke the existing key and generate a new one in a single atomic operation. Returns the new raw key.
**Why:** Key rotation is a security best practice. Currently, users must manually delete and recreate keys, which creates a window where no key is active. Rotation makes this seamless.
**Where:** `api/routers/auth.py`, `persistence/api_key_repository.py`
**Effort:** S | **Priority:** P2

---

## Infrastructure (P1) — DONE

### ~~Dockerfile + docker-compose~~ ✓
Implemented: `Dockerfile` with uv, `docker-compose.yml` with app + postgres + migrate service, `.dockerignore`.

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
