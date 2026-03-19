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

### ~~Usage analytics endpoints~~ ✓
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

### ~~API key rotation / re-generation~~ ✓
Implemented: `POST /auth/api-keys/{id}/rotate` in `api/routers/auth.py` + atomic `APIKeyRepository.rotate()` (revokes active key, creates replacement key row in one transaction) with unit coverage in router and persistence tests.

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

## Quality of life (P3)

### Conversation export (Markdown/PDF)
**What:** Export a full conversation thread as a Markdown file or downloadable PDF from the UI.
**Why:** Useful for saving research outputs, sharing code review feedback, or archiving important assistant responses.
**Where:** `ui/src/pages/ConversationView.tsx` — add an export button that fetches messages and formats them. PDF via `@react-pdf/renderer` or browser `window.print()`.
**Effort:** S (human: ~4 hours / CC: ~10 min) | **Priority:** P3
**Depends on:** Web UI baseline (conversation history view must exist first).

---

## UI Design Debt (from /plan-design-review 2026-03-19)

### Inline confirmation pattern (replace confirm() dialogs) — P2
**What:** Replace native `confirm()` on workspace delete and API key revoke with an inline "Are you sure? [Cancel] [Delete]" row within the card.
**Why:** Native `confirm()` ignores dark mode, looks like a system alert, and is jarring against the polished card UI. Breaks trust at the pixel level.
**Pros:** Consistent dark mode; fits the design language; no extra library needed.
**Cons:** A few lines of `confirming: string | null` state per page.
**Where:** `ui/src/pages/WorkspaceList.tsx`, `ui/src/pages/ApiKeys.tsx`
**Effort:** XS (human: ~2 hours / CC: ~5 min) | **Priority:** P2
**Depends on:** None

### Accessibility — aria-live, touch targets, form labels — P2
**What:** (1) `aria-live="polite"` on the chat message container for streaming. (2) `min-h-[44px]` on all action buttons currently under 44px (History, Delete, Revoke, sidebar hamburger). (3) Explicit `htmlFor`/`id` associations on all form labels.
**Why:** Screen readers can't follow streaming chat. Small buttons cause mis-taps on mobile. Forms without `htmlFor` break autofill and screen readers.
**Where:** `ui/src/pages/Chat.tsx`, `ui/src/pages/WorkspaceList.tsx`, `ui/src/pages/ApiKeys.tsx`, `ui/src/pages/AgentConfig.tsx`, `ui/src/pages/Login.tsx`, `ui/src/components/Layout.tsx`
**Effort:** S (human: ~4 hours / CC: ~15 min) | **Priority:** P2
**Depends on:** None

### Resume last conversation on login — P2
**What:** After login (and when visiting `/` while already authenticated), skip the workspace picker entirely. Auto-select the most recently updated workspace and redirect directly to the most recent conversation in it. The user should never have to choose a workspace to start chatting.
- After login or register: resolve the smart redirect and navigate there instead of `/workspaces`.
- Index route (`/`): replaced with a `<SmartRedirect />` component that performs the same resolution for users who land on `/` while already authenticated.
- Resolution order: most recent workspace (by `updated_at`) → most recent conversation in that workspace → `/workspaces/{name}/chat/{id}`. Falls back to `/workspaces/{name}/chat` (new conversation) if no prior conversation exists. Falls back to `/workspaces` if the user has no workspaces yet.
**Why:** The plan vision says "Open it and your most recent conversation is already there." Currently users must click through the workspace picker on every login. Eliminating that step delivers the vision and reduces daily friction.
**Pros:** Delivers the stated vision; removes the mandatory workspace-picker click; applies to both login and direct URL visits.
**Cons:** Adds 2 extra API calls at login/index-route; needs handling for deleted workspaces and no-conversation edge cases (handled via try/catch fallback to `/workspaces`).
**Where:** `ui/src/contexts/AuthContext.tsx` (exported `getSmartRedirectPath()` utility), `ui/src/pages/Login.tsx`, `ui/src/App.tsx` (`<SmartRedirect />` index component)
**Effort:** S (human: ~3 hours / CC: ~10 min) | **Priority:** P2
**Depends on:** None

### ConversationHistory responsive split-pane — P2
**What:** The left panel (`w-72 flex-shrink-0`) overflows on mobile. Fix: `flex-col lg:flex-row` wrapper; on mobile, show list on top with a collapsible preview below (or back-button pattern matching the sidebar).
**Why:** The plan accepted mobile responsive layout. ConversationHistory is the one page that missed it.
**Where:** `ui/src/pages/ConversationHistory.tsx`
**Effort:** S (human: ~2 hours / CC: ~10 min) | **Priority:** P2
**Depends on:** None

---

## Roadmap (previously documented)

- **Supervisor streaming** — LangGraph graph-level streaming for workspace chat without requiring `agent_name`. Blocked by LangGraph supervisor graph streaming support.
- **Redis-backed conversation cache** — drop-in replacement for `InMemoryConversationCache`. Unblocks multi-process deployment and the concurrent chat race condition fix.
- **More providers** — OpenAI, Groq, Google Gemini. Each is a `AIProvider` subclass + entry in `build_registry()`.
- **~~Web UI~~** ✓ — Completed in v0.1.1. React + TypeScript application with chat interface, workspace/agent management, usage dashboard, API key management, command palette, dark mode, responsive design, and conversation search. **Completed:** v0.1.1 (2026-03-19)
