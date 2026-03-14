# Personal Assistant

[![Tests](https://github.com/lestherll/personal_assistant/actions/workflows/tests.yml/badge.svg)](https://github.com/lestherll/personal_assistant/actions/workflows/tests.yml)

A modular AI personal assistant built on [LangChain](https://www.langchain.com/) and [LangGraph](https://www.langchain.com/langgraph). The core idea is configurable AI agents that specialise in specific tasks, grouped into workspaces, backed by a pluggable provider registry — making it easy to swap models, extend with new tools, and expose as an API.

---

## Features

- **Provider registry** — plug in any LLM backend (Anthropic, Ollama, and more to come) and switch between them per-agent
- **Configurable agents** — each agent has its own system prompt, provider, model, and tool allowlist
- **Persistent conversation history** — agents remember context across turns within a session
- **Workspaces** — group agents and tools together; tools auto-register with compatible agents
- **Runtime agent switching** — hot-swap an agent's model, prompt, or provider without restarting
- **Extensible tools** — add new tools by subclassing `AssistantTool`

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
# Edit .env and add your ANTHROPIC_API_KEY

# Run the REPL
uv run python main.py
```

---

## Project Structure

```
personal_assistant/
├── core/
│   ├── agent.py          # Agent + AgentConfig (LangGraph ReAct loop, history)
│   ├── tool.py           # AssistantTool base class
│   ├── workspace.py      # Workspace — groups agents and tools
│   └── orchestrator.py   # Orchestrator — manages workspaces and routes tasks
├── providers/
│   ├── base.py           # AIProvider + ProviderConfig abstract base
│   ├── registry.py       # ProviderRegistry — named lookup with default
│   ├── anthropic.py      # AnthropicProvider (Claude via langchain-anthropic)
│   └── ollama.py         # OllamaProvider (local models via langchain-ollama)
├── agents/
│   └── assistant_agent.py  # General-purpose starter agent
├── tools/
│   └── example_tool.py     # EchoTool — template for building new tools
└── workspaces/
    └── default_workspace.py  # Default workspace factory
main.py                       # Entry point — REPL
```

---

## Configuration

Create a `.env` file in the project root:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

Ollama runs locally at `http://localhost:11434` by default. Pull a model before using it:

```bash
ollama pull llama3.2
```

---

## Usage

### Basic REPL

```bash
uv run python main.py
```

### Switching providers

```python
from personal_assistant.providers import (
    ProviderRegistry, AnthropicProvider, OllamaProvider, OllamaConfig
)

registry = ProviderRegistry()
registry.register(AnthropicProvider(), default=True)
registry.register(OllamaProvider(OllamaConfig(default_model="llama3.2")))
```

### Creating a custom agent

```python
from personal_assistant.core.agent import AgentConfig
from personal_assistant.core.orchestrator import Orchestrator

orchestrator = Orchestrator(registry)
workspace = orchestrator.create_workspace(WorkspaceConfig(name="research", description="..."))

orchestrator.create_agent(AgentConfig(
    name="Researcher",
    description="In-depth research assistant",
    system_prompt="You are a research assistant. Be thorough and cite your reasoning.",
    provider="ollama",
    model="llama3.2",
))

response = orchestrator.delegate("Explain transformer attention mechanisms", agent_name="Researcher")
```

### Hot-swapping an agent at runtime

```python
orchestrator.replace_agent(AgentConfig(
    name="Assistant",
    description="Terse assistant",
    system_prompt="You are a terse assistant. One sentence max.",
    provider="anthropic",
    model="claude-opus-4-6",
))
```

### Adding a custom tool

```python
from pydantic import BaseModel, Field
from personal_assistant.core.tool import AssistantTool

class WeatherInput(BaseModel):
    location: str = Field(description="City name to get weather for.")

class WeatherTool(AssistantTool):
    name: str = "get_weather"
    description: str = "Get the current weather for a location."
    args_schema: type[BaseModel] = WeatherInput

    def _run(self, location: str) -> str:
        return f"It's sunny and 22°C in {location}."

workspace.add_tool(WeatherTool())  # auto-registers with all agents in the workspace
```

---

## Development

```bash
# Install dev dependencies
uv sync

# Run tests
uv run pytest

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run mypy personal_assistant
```

---

## Roadmap

- [ ] FastAPI layer — expose as an HTTP API with session management and SSE streaming
- [ ] More providers — OpenAI, Groq, Google Gemini
- [ ] Persistent sessions — save and restore conversation history
- [ ] Web UI
