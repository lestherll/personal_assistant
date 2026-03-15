# Personal Assistant

[![Tests](https://github.com/lestherll/personal_assistant/actions/workflows/tests.yml/badge.svg)](https://github.com/lestherll/personal_assistant/actions/workflows/tests.yml)
[![Security](https://github.com/lestherll/personal_assistant/actions/workflows/security.yml/badge.svg)](https://github.com/lestherll/personal_assistant/actions/workflows/security.yml)

A modular AI personal assistant built on [LangChain](https://www.langchain.com/) and [LangGraph](https://www.langchain.com/langgraph). Configurable agents specialise in specific tasks, are grouped into workspaces, and are backed by a pluggable provider registry — making it easy to swap models, extend with new tools, and expose everything over an HTTP API.

---

## Features

- **Multiple AI providers** — Anthropic (Claude) and Ollama (local models) out of the box
- **Configurable agents** — each agent has its own system prompt, provider, model, and tool allowlist
- **Workspaces** — group agents and tools together; the workspace supervisor automatically routes each message to the best agent
- **Flexible chat** — target the supervisor for automatic routing, or name a specific agent to bypass it; override the provider and model per request without changing the agent's saved configuration
- **Streaming responses** — SSE streaming for both agent-direct and workspace-level chat
- **Persistent conversation history** — agents remember context across turns; resumable via `conversation_id`
- **Optional PostgreSQL persistence** — conversation and message history backed by SQLAlchemy + asyncpg; fully in-memory without a database configured
- **REST API** — FastAPI with full OpenAPI docs, typed request/response schemas, and structured error responses
- **Extensible tools** — add new tools by subclassing `AssistantTool`; tools auto-register with all compatible agents in a workspace

---

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) for package management
- [Ollama](https://ollama.com) for local models (optional)
- An Anthropic API key for Claude models (optional)

---

## Quickstart

```bash
# Clone and install dependencies
git clone git@github.com:lestherll/personal_assistant.git
cd personal_assistant
uv sync

# Set up environment
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY and/or configure Ollama

# Start the REST API
uv run fastapi dev api/main.py

# Or start the interactive REPL
uv run python main.py
```

---

## API Overview

The REST API is documented at `http://localhost:8000/docs` when running in dev mode.

Key endpoints:

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Register a new user |
| `POST` | `/auth/login` | Log in and get tokens |
| `GET` | `/providers/` | List registered AI providers |
| `GET` | `/providers/{name}/models` | List models for a provider |
| `POST` | `/workspaces/` | Create a workspace |
| `GET` | `/workspaces/` | List workspaces |
| `POST` | `/workspaces/{name}/chat` | Workspace chat (supervisor or agent-direct) |
| `POST` | `/workspaces/{name}/chat/stream` | Streaming workspace chat |
| `POST` | `/workspaces/{name}/agents/` | Create an agent |
| `POST` | `/workspaces/{name}/agents/{agent}/chat` | Direct agent chat |
| `POST` | `/workspaces/{name}/agents/{agent}/chat/stream` | Streaming agent chat |

All endpoints except `/auth/**` and `/health` require `Authorization: Bearer <token>`. Set `AUTH_DISABLED=true` in `.env` to skip auth in development.

---

## Environment

Copy `.env.example` to `.env` and configure:

```env
ANTHROPIC_API_KEY=sk-ant-...           # Claude models
RAPIDAPI_KEY=...                       # optional — enables job search tool
DATABASE_URL=postgresql+asyncpg://...  # optional — enables conversation persistence
SECRET_KEY=<random-32-bytes>           # generate: openssl rand -hex 32
AUTH_DISABLED=false                    # set true to skip auth (dev only)
```

Ollama runs locally at `http://localhost:11434` by default. Pull a model before using it:

```bash
ollama pull qwen2.5:14b
```

---

## Development

```bash
uv run pytest              # unit + functional tests
uv run ruff check .        # lint
uv run ruff format .       # format
uv run mypy . --exclude tests  # type check
uv run alembic upgrade head    # apply DB migrations
```

See [CLAUDE.md](CLAUDE.md) for the full developer guide and [ARCHITECTURE.md](ARCHITECTURE.md) for the system design.

---

## Roadmap

- [ ] More providers — OpenAI, Groq, Google Gemini
- [ ] Web UI
- [ ] Supervisor streaming (LangGraph graph-level)
- [ ] Redis-backed conversation cache
