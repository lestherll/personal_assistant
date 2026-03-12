from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

if TYPE_CHECKING:
    from personal_assistant.providers.registry import ProviderRegistry


@dataclass
class AgentConfig:
    name: str
    description: str
    system_prompt: str
    provider: str | None = None  # Registry key — None means use the registry default
    model: str | None = None  # Model name — None means use the provider's default
    # Names of tools this agent is allowed to use (empty = accept all added tools)
    allowed_tools: list[str] = field(default_factory=list)


class Agent:
    """A configurable AI agent backed by a LangGraph ReAct loop.

    Agents are specialised for specific tasks via their system prompt and
    the tools they are given. The LLM can be resolved from a ProviderRegistry
    or provided directly as a resolved LLM instance.

    Creation patterns:
        # Via registry (backward compatible):
        agent = Agent(config, registry)

        # Via factory with registry:
        agent = Agent.from_config(config, registry)

        # Via factory with resolved LLM (standalone):
        agent = Agent.from_llm(config, llm)
    """

    def __init__(
        self,
        config: AgentConfig,
        registry: ProviderRegistry | None = None,
        *,
        llm: BaseChatModel | None = None,
    ) -> None:
        """Initialize an Agent.

        Args:
            config: Agent configuration.
            registry: Provider registry for resolving LLM. Required if llm is not provided.
            llm: Pre-resolved LLM instance. If provided, registry is ignored.

        Raises:
            ValueError: If neither registry nor llm is provided.
        """
        if llm is None and registry is None:
            raise ValueError("Either 'registry' or 'llm' must be provided")

        self.config = config
        self._registry = registry
        self._tools: list[BaseTool] = []
        self._history: list[BaseMessage] = []
        self._dirty = True  # Track if graph needs rebuild
        self._llm: BaseChatModel

        if llm is not None:
            self._llm = llm
        else:
            # registry is guaranteed non-None by the check above
            self._llm = registry.get(config.provider).get_model(config.model)

        self._graph: Any = self._build_graph()

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config: AgentConfig, registry: ProviderRegistry) -> Agent:
        """Create an Agent from config using a ProviderRegistry.

        This is the standard pattern for creating agents within the orchestrator.

        Args:
            config: Agent configuration.
            registry: Provider registry for resolving LLM.

        Returns:
            A new Agent instance.
        """
        return cls(config, registry=registry)

    @classmethod
    def from_llm(cls, config: AgentConfig, llm: BaseChatModel) -> Agent:
        """Create a standalone Agent with a pre-resolved LLM.

        This pattern allows agents to exist independently of the ProviderRegistry,
        useful for testing or when the LLM is constructed externally.

        Args:
            config: Agent configuration.
            llm: Pre-resolved LLM instance.

        Returns:
            A new Agent instance.
        """
        return cls(config, llm=llm)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_graph(self) -> Any:
        self._dirty = False
        return create_react_agent(
            model=self._llm,
            tools=self._tools,
            prompt=self.config.system_prompt,
        )

    def _ensure_graph(self) -> None:
        """Rebuild the graph if it's dirty."""
        if self._dirty:
            self._graph = self._build_graph()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_tool(self, tool: BaseTool) -> None:
        """Add a tool to this agent.

        The graph is marked dirty and will be rebuilt on the next run() call.
        """
        if self.config.allowed_tools and tool.name not in self.config.allowed_tools:
            return
        if any(t.name == tool.name for t in self._tools):
            return
        self._tools.append(tool)
        self._dirty = True

    def remove_tool(self, tool_name: str) -> None:
        """Remove a tool by name.

        The graph is marked dirty and will be rebuilt on the next run() call.
        """
        self._tools = [t for t in self._tools if t.name != tool_name]
        self._dirty = True

    def rebuild_graph(self) -> None:
        """Explicitly rebuild the execution graph.

        Useful after bulk tool operations to control when the rebuild happens.
        """
        self._graph = self._build_graph()

    @contextmanager
    def batch_tools(self) -> Iterator[None]:
        """Context manager for batch tool operations.

        Defers graph rebuild until the context exits, improving efficiency
        when adding/removing multiple tools.

        Example:
            with agent.batch_tools():
                agent.register_tool(tool1)
                agent.register_tool(tool2)
                agent.remove_tool("old_tool")
            # Graph is rebuilt once here
        """
        yield
        self.rebuild_graph()

    @property
    def tools(self) -> list[str]:
        return [t.name for t in self._tools]

    def run(self, task: str) -> str:
        """Run a task and return the agent's final text response.

        Automatically rebuilds the graph if tools have changed since last run.
        """
        self._ensure_graph()
        self._history.append(HumanMessage(content=task))
        result = self._graph.invoke({"messages": self._history})
        self._history = result["messages"]
        content = self._history[-1].content
        return content if isinstance(content, str) else str(content)

    def stream(self, task: str) -> Iterator[BaseMessage]:
        """Stream agent messages as they are produced.

        Automatically rebuilds the graph if tools have changed since last stream.
        """
        self._ensure_graph()
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
