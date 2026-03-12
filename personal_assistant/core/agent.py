from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

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

    Agents are specialised for specific tasks via their system prompt and
    the tools they are given. The LLM is resolved from the ProviderRegistry,
    so swapping providers (e.g. Anthropic → Ollama) requires no agent changes.

    Persistence is opt-in: pass a SQLAlchemy ``AsyncSession`` to ``run()`` or
    ``stream()`` to automatically save messages.  Call ``start_conversation()``
    first to create a new conversation row, or set ``conversation_id`` to
    resume an existing one.
    """

    def __init__(self, config: AgentConfig, registry: ProviderRegistry) -> None:
        self.config = config
        self._registry = registry
        self._tools: list[BaseTool] = []
        self._history: list[BaseMessage] = []
        self._conversation_id: uuid.UUID | None = None
        self._history_loaded: bool = False
        self._llm = registry.get(config.provider).get_model(config.model)
        self._graph: Any = self._build_graph()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_graph(self) -> Any:
        return create_react_agent(
            model=self._llm,
            tools=self._tools,
            prompt=self.config.system_prompt,
        )

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
        """Run a task and return the agent's final text response."""
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
        """Stream agent messages as they are produced."""
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
