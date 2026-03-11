from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

if TYPE_CHECKING:
    from ..providers.registry import ProviderRegistry


@dataclass
class AgentConfig:
    name: str
    description: str
    system_prompt: str
    provider: str | None = None   # Registry key — None means use the registry default
    model: str | None = None      # Model name — None means use the provider's default
    # Names of tools this agent is allowed to use (empty = accept all added tools)
    allowed_tools: list[str] = field(default_factory=list)


class Agent:
    """A configurable AI agent backed by a LangGraph ReAct loop.

    Agents are specialised for specific tasks via their system prompt and
    the tools they are given. The LLM is resolved from the ProviderRegistry,
    so swapping providers (e.g. Anthropic → Ollama) requires no agent changes.
    """

    def __init__(self, config: AgentConfig, registry: ProviderRegistry) -> None:
        self.config = config
        self._registry = registry
        self._tools: list[BaseTool] = []
        self._history: list[BaseMessage] = []
        self._llm = registry.get(config.provider).get_model(config.model)
        self._graph = self._build_graph()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_graph(self):
        return create_react_agent(
            model=self._llm,
            tools=self._tools,
            prompt=self.config.system_prompt,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_tool(self, tool: BaseTool) -> None:
        """Add a tool to this agent and rebuild the execution graph."""
        if self.config.allowed_tools and tool.name not in self.config.allowed_tools:
            return
        if any(t.name == tool.name for t in self._tools):
            return
        self._tools.append(tool)
        self._graph = self._build_graph()

    def remove_tool(self, tool_name: str) -> None:
        """Remove a tool by name and rebuild the execution graph."""
        self._tools = [t for t in self._tools if t.name != tool_name]
        self._graph = self._build_graph()

    @property
    def tools(self) -> list[str]:
        return [t.name for t in self._tools]

    def run(self, task: str) -> str:
        """Run a task and return the agent's final text response."""
        self._history.append(HumanMessage(content=task))
        result = self._graph.invoke({"messages": self._history})
        # Replace history with the full updated message list (includes tool calls etc.)
        self._history = result["messages"]
        return self._history[-1].content

    def stream(self, task: str):
        """Stream agent messages as they are produced."""
        self._history.append(HumanMessage(content=task))
        for chunk in self._graph.stream(
            {"messages": self._history},
            stream_mode="values",
        ):
            self._history = chunk["messages"]
            yield self._history[-1]

    def reset(self) -> None:
        """Clear conversation history."""
        self._history = []

    @property
    def history(self) -> list[BaseMessage]:
        return list(self._history)
