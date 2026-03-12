from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from personal_assistant.persistence.models import Message as MessageRow
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

    The LLM can be resolved from a ProviderRegistry or provided directly.

    Creation patterns:
        # Via registry (backward compatible):
        agent = Agent(config, registry)

        # Via factory with registry:
        agent = Agent.from_config(config, registry)

        # Via factory with resolved LLM (standalone):
        agent = Agent.from_llm(config, llm)

    Persistence is opt-in: pass a SQLAlchemy ``AsyncSession`` to ``run()`` or
    ``stream()`` to automatically save messages.  Call ``start_conversation()``
    first to create a new conversation row, or set ``conversation_id`` to
    resume an existing one.
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
        self._conversation_id: uuid.UUID | None = None
        self._history_loaded: bool = False
        self._dirty = True  # Track if graph needs rebuild
        self._llm: BaseChatModel

        if llm is not None:
            self._llm = llm
        else:
            assert registry is not None  # guaranteed by the check above
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

    async def _ensure_history_loaded(self, session: AsyncSession | None) -> None:
        """Lazily restore conversation history from the DB on the first call."""
        if self._history_loaded or self._conversation_id is None or session is None:
            return
        from personal_assistant.persistence.repository import ConversationRepository

        repo = ConversationRepository(session)
        rows = await repo.load_messages(self._conversation_id)
        self._history = [_row_to_message(row) for row in rows]
        self._history_loaded = True

    # ------------------------------------------------------------------
    # Public API — tool management
    # ------------------------------------------------------------------

    def register_tool(self, tool: BaseTool) -> None:
        """Add a tool to this agent.

        If the tool declares an ``agent_config`` field, a copy is created with
        this agent's config bound to it before registration.

        The graph is marked dirty and will be rebuilt on the next run() call.
        """
        if self.config.allowed_tools and tool.name not in self.config.allowed_tools:
            return
        if any(t.name == tool.name for t in self._tools):
            return
        if "agent_config" in getattr(type(tool), "model_fields", {}):
            tool = tool.model_copy(update={"agent_config": self.config})
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
        when adding/removing multiple tools. The graph is always rebuilt on
        exit, even if an exception is raised inside the block.

        Example:
            with agent.batch_tools():
                agent.register_tool(tool1)
                agent.register_tool(tool2)
                agent.remove_tool("old_tool")
            # Graph is rebuilt once here
        """
        try:
            yield
        finally:
            self.rebuild_graph()

    @property
    def tools(self) -> list[str]:
        return [t.name for t in self._tools]

    # ------------------------------------------------------------------
    # Public API — LLM management
    # ------------------------------------------------------------------

    def get_llm_info(self) -> dict[str, str | None]:
        """Return information about the underlying LLM regardless of creation path.

        When created via registry, returns the configured provider and model names.
        When created via from_llm(), infers the class name and model attribute from
        the LLM instance, since no provider/model strings were provided at construction.

        Returns:
            A dict with keys 'provider', 'model', and 'source' ('registry' or 'direct').
        """
        if self._registry is not None:
            return {
                "provider": self.config.provider,
                "model": self.config.model,
                "source": "registry",
            }
        model_attr = getattr(self._llm, "model_name", None) or getattr(self._llm, "model", None)
        return {
            "provider": type(self._llm).__name__,
            "model": model_attr,
            "source": "direct",
        }

    def set_llm(self, llm: BaseChatModel) -> None:
        """Swap the underlying LLM and rebuild the graph immediately.

        Useful for hot-swapping providers on standalone agents at runtime.
        After calling this, the agent no longer references a ProviderRegistry.

        Args:
            llm: The new LLM instance to use.
        """
        self._llm = llm
        self._registry = None
        self._graph = self._build_graph()

    # ------------------------------------------------------------------
    # Public API — persistence
    # ------------------------------------------------------------------

    @property
    def conversation_id(self) -> uuid.UUID | None:
        return self._conversation_id

    @conversation_id.setter
    def conversation_id(self, value: uuid.UUID | None) -> None:
        """Bind this agent to an existing conversation (history loaded lazily)."""
        self._conversation_id = value
        self._history_loaded = False
        self._history = []

    async def start_conversation(
        self, session: AsyncSession, workspace_name: str | None = None
    ) -> uuid.UUID:
        """Create a new conversation in the DB and bind this agent to it.

        Returns the new conversation's UUID.
        """
        from personal_assistant.persistence.repository import ConversationRepository

        repo = ConversationRepository(session)
        conv = await repo.create_conversation(self.config.name, workspace_name)
        self._conversation_id = conv.id
        self._history_loaded = True  # Fresh conversation — nothing to load
        self._history = []
        return conv.id

    # ------------------------------------------------------------------
    # Public API — inference
    # ------------------------------------------------------------------

    async def run(self, task: str, session: AsyncSession | None = None) -> str:
        """Run a task and return the agent's final text response.

        Automatically rebuilds the graph if tools have changed since last run.
        """
        self._ensure_graph()
        await self._ensure_history_loaded(session)
        self._history.append(HumanMessage(content=task))

        if session is not None and self._conversation_id is not None:
            from personal_assistant.persistence.repository import ConversationRepository

            repo = ConversationRepository(session)
            await repo.save_message(self._conversation_id, "human", task)

        result = await self._graph.ainvoke({"messages": self._history})
        self._history = result["messages"]
        content = self._history[-1].content
        response = content if isinstance(content, str) else str(content)

        if session is not None and self._conversation_id is not None:
            repo = ConversationRepository(session)
            await repo.save_message(self._conversation_id, "ai", response)
            await repo.touch_conversation(self._conversation_id)

        return response

    async def stream(
        self, task: str, session: AsyncSession | None = None
    ) -> AsyncIterator[BaseMessage]:
        """Stream agent messages as they are produced.

        Automatically rebuilds the graph if tools have changed since last stream.
        """
        self._ensure_graph()
        await self._ensure_history_loaded(session)
        self._history.append(HumanMessage(content=task))

        if session is not None and self._conversation_id is not None:
            from personal_assistant.persistence.repository import ConversationRepository

            repo = ConversationRepository(session)
            await repo.save_message(self._conversation_id, "human", task)

        async for chunk in self._graph.astream(
            {"messages": self._history},
            stream_mode="values",
        ):
            self._history = chunk["messages"]
            yield self._history[-1]

        # Persist the final AI message after streaming completes
        if session is not None and self._conversation_id is not None and self._history:
            last = self._history[-1]
            if isinstance(last, AIMessage):
                ai_content = last.content if isinstance(last.content, str) else str(last.content)
                repo = ConversationRepository(session)
                await repo.save_message(self._conversation_id, "ai", ai_content)
                await repo.touch_conversation(self._conversation_id)

    def reset(self) -> None:
        """Clear in-memory conversation history.

        Does *not* delete rows from the database — use the repository directly
        if you need to purge persisted messages.
        """
        self._history = []
        self._conversation_id = None
        self._history_loaded = False

    @property
    def history(self) -> list[BaseMessage]:
        return list(self._history)


def _row_to_message(row: MessageRow) -> BaseMessage:
    """Convert a persisted Message row back to a LangChain BaseMessage."""
    if row.role == "human":
        return HumanMessage(content=row.content)
    return AIMessage(content=row.content)
