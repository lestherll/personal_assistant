# Personal Assistant

[![Tests](https://github.com/lestherll/personal_assistant/actions/workflows/tests.yml/badge.svg)](https://github.com/lestherll/personal_assistant/actions/workflows/tests.yml)
[![Security](https://github.com/lestherll/personal_assistant/actions/workflows/security.yml/badge.svg)](https://github.com/lestherll/personal_assistant/actions/workflows/security.yml)

A modular AI personal assistant built on [LangChain](https://www.langchain.com/) and [LangGraph](https://www.langchain.com/langgraph). Configurable agents specialise in specific tasks, are grouped into workspaces, and are backed by a pluggable provider registry — making it easy to swap models, extend with new tools, and expose everything over an HTTP API.

---

## Features

- **Multiple AI providers** — Anthropic (Claude) and Ollama (local models) out of the box; discover available models at runtime via `/providers`
- **Configurable agents** — each agent has its own system prompt, provider, model, and tool allowlist
- **Workspaces** — group agents and tools together; the workspace supervisor automatically routes each message to the best agent
- **Flexible workspace chat** — target the supervisor for automatic routing, or name a specific agent to skip it; override the provider and model per request without changing the agent's configuration
- **Streaming responses** — SSE streaming for both per-agent and workspace-level chat
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
# Edit .env — add ANTHROPIC_API_KEY and/or leave blank to use Ollama only

# Start the REST API
uv run fastapi dev api/main.py

# Or start the interactive REPL
uv run python main.py
```

---

## API Usage

### Discover providers and models

```bash
curl http://localhost:8000/providers/
curl http://localhost:8000/providers/anthropic/models
curl http://localhost:8000/providers/ollama/models
```

### Workspace chat — automatic agent routing

The supervisor reads each agent's description and routes the message to the most suitable one.

```bash
curl -X POST http://localhost:8000/workspaces/default/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Help me write a cover letter."}'
```

```json
{
  "response": "...",
  "conversation_id": "a3f1c2d4-...",
  "agent_used": "Career"
}
```

Pass `conversation_id` back on subsequent turns to continue the conversation.

### Workspace chat — target a specific agent

Skip the supervisor and route directly to a named agent.

```bash
curl -X POST http://localhost:8000/workspaces/default/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Review this Python function.", "agent_name": "Coding"}'
```

### Override the model for a single request

Use a different provider or model for one turn without changing the agent's saved configuration.

```bash
curl -X POST http://localhost:8000/workspaces/default/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Summarise this article.",
    "agent_name": "Research",
    "provider": "anthropic",
    "model": "claude-haiku-4-5-20251001"
  }'
```

### Streaming workspace chat

```bash
curl -N -X POST http://localhost:8000/workspaces/default/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me a joke.", "agent_name": "Assistant"}'
```

Response headers carry `X-Conversation-Id` and `X-Agent-Used`. The body is a standard SSE stream (`data: {token}\n\n`) terminated by `data: [DONE]\n\n`.

### Per-agent chat

Target an agent directly without going through the workspace.

```bash
# Non-streaming
curl -X POST http://localhost:8000/workspaces/default/agents/Assistant/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'

# Streaming
curl -N -X POST http://localhost:8000/workspaces/default/agents/Assistant/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'
```

### Create a workspace and agent via the API

```bash
# Create a workspace
curl -X POST http://localhost:8000/workspaces/ \
  -H "Content-Type: application/json" \
  -d '{"name": "research", "description": "Research workspace"}'

# Create an agent in it
curl -X POST http://localhost:8000/workspaces/research/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Analyst",
    "description": "Data and market analyst",
    "system_prompt": "You are a data analyst. Be precise and cite evidence.",
    "provider": "anthropic",
    "model": "claude-sonnet-4-6"
  }'
```

---

## Environment

Copy `.env.example` to `.env` and configure:

```env
ANTHROPIC_API_KEY=sk-ant-...           # Claude models
RAPIDAPI_KEY=...                       # optional — enables job search tool
DATABASE_URL=postgresql+asyncpg://...  # optional — enables conversation persistence
```

Ollama runs locally at `http://localhost:11434` by default. Pull a model before using it:

```bash
ollama pull llama3.2
```

---

## Development

```bash
uv run pytest              # unit + functional tests
uv run ruff check .        # lint
uv run ruff format .       # format
uv run mypy . --exclude tests  # type check
```

See [CLAUDE.md](CLAUDE.md) for the full developer guide and [ARCHITECTURE.md](ARCHITECTURE.md) for the system design.

---

## Roadmap

- [ ] More providers — OpenAI, Groq, Google Gemini
- [ ] Web UI
- [ ] Multi-turn model override support (pool keyed by model)
- [ ] Supervisor streaming (LangGraph graph-level)
