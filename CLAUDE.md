# Personal Assistant — CLAUDE.md

## Project Overview

A modular AI personal assistant built on LangChain and LangGraph. The core concept is configurable AI agents that specialise in specific tasks, grouped into workspaces, backed by a pluggable AI provider registry.

## Stack

- **Python 3.13**, managed with **uv**
- **LangChain** + **LangGraph** — agent orchestration (ReAct loop via `create_react_agent`)
- **langchain-anthropic** — Anthropic/Claude provider
- **langchain-ollama** — Ollama local provider
- **python-dotenv** — `.env` loading
- **pydantic v2** — tool input schemas

## Project Structure

```
personal_assistant/
├── core/
│   ├── agent.py          # Agent + AgentConfig — LangGraph ReAct agent with history
│   ├── tool.py           # AssistantTool base class (extends LangChain BaseTool)
│   ├── workspace.py      # Workspace — groups agents + tools, auto-registers tools
│   └── orchestrator.py   # Orchestrator — manages registry, workspaces, task routing
├── providers/
│   ├── base.py           # AIProvider + ProviderConfig abstract base
│   ├── registry.py       # ProviderRegistry — named provider lookup + default
│   ├── anthropic.py      # AnthropicProvider (ChatAnthropic)
│   └── ollama.py         # OllamaProvider (ChatOllama, local)
├── agents/
│   └── assistant_agent.py  # AssistantAgent — general-purpose starter agent
├── tools/
│   └── example_tool.py     # EchoTool — template for new tools
└── workspaces/
    └── default_workspace.py  # Factory: wires default agent + tools into a workspace
main.py                       # Entry point — bootstraps registry, orchestrator, REPL
```

## Key Concepts

### Providers
Registered in a `ProviderRegistry` by name. Each provider wraps a LangChain chat model and exposes `get_model(model, **kwargs)`. Add new providers by subclassing `AIProvider`.

### Agents
Created from `AgentConfig` (name, description, system_prompt, provider, model, allowed_tools). Maintain their own conversation history across turns. Rebuilt automatically when tools are added/removed.

### Workspaces
Named containers for agents and tools. Tools added to a workspace are auto-registered with all compatible agents. Supports `add_agent`, `remove_agent`, `replace_agent`, `add_tool`, `remove_tool`.

### Orchestrator
Owns the `ProviderRegistry` and all workspaces. Routes tasks via `delegate(task, agent_name, workspace_name)`. Helpers: `create_agent(config)`, `replace_agent(config)`.

## Environment

Copy `.env.example` to `.env` and set:
```
ANTHROPIC_API_KEY=sk-ant-...
```

Ollama runs locally at `http://localhost:11434`. Pull models with `ollama pull <model>`.

## Commands

```bash
uv run python main.py        # Start the REPL
uv add <package>             # Add a dependency
```

## Conventions

- New tools: subclass `AssistantTool` in `personal_assistant/tools/`, define `name`, `description`, `args_schema` (Pydantic model), and `_run()`.
- New agents: subclass `Agent` or use `AgentConfig` directly with `orchestrator.create_agent()`.
- New providers: subclass `AIProvider` in `personal_assistant/providers/`, implement `get_model()`, register in `main.py`.
- New workspaces: add a factory function in `personal_assistant/workspaces/`.
- Do not hardcode API keys — always use `.env`.
- Agent conversation history persists per agent instance. Call `agent.reset()` to clear.
