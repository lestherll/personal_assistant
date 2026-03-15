from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any, NotRequired

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command
from pydantic import BaseModel
from typing_extensions import TypedDict

from personal_assistant.core.agent import Agent

if TYPE_CHECKING:
    pass


@dataclass
class AgentInfo:
    """Lightweight agent descriptor used by the stateless router."""

    name: str
    description: str


async def route(message: str, agents: list[AgentInfo], llm: BaseChatModel) -> str:
    """Return the name of the best agent to handle *message*.

    Makes a single structured LLM call — no LangGraph graph, no checkpointer.
    Falls back to the first agent if the LLM returns an unexpected value.
    """
    agent_descriptions = "\n".join(f"- {a.name}: {a.description}" for a in agents)
    valid_names = [a.name for a in agents]

    class _Decision(BaseModel):
        next_agent: str

    router_llm = llm.with_structured_output(_Decision)
    system = SystemMessage(
        content=(
            "You are a routing supervisor. Pick the most suitable agent for the "
            "user's request.\n\n"
            f"Available agents:\n{agent_descriptions}\n\n"
            f"Respond with exactly one agent name from: {', '.join(valid_names)}."
        )
    )
    result = await router_llm.ainvoke([system, HumanMessage(content=message)])
    chosen: str = getattr(result, "next_agent", "")
    return chosen if chosen in valid_names else valid_names[0]


class _RouterDecision(BaseModel):
    next_agent: str


class _WorkspaceState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    agent_used: NotRequired[str]


class WorkspaceSupervisor:
    """Builds and holds the supervisor StateGraph for a workspace.

    Each workspace has one supervisor that routes incoming messages to the
    most suitable agent via a LangGraph StateGraph.  Conversation state
    (message history) is maintained across turns by LangGraph's
    ``MemorySaver`` checkpointer, keyed by ``thread_id``.
    """

    def __init__(self, agents: list[Agent], llm: BaseChatModel) -> None:
        self._agents: list[Agent] = agents
        self._llm = llm
        self._checkpointer: MemorySaver = MemorySaver()
        self._graph: Any = self._build()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build(self) -> Any:
        """Build (or rebuild) the supervisor StateGraph."""
        agents = self._agents
        agent_names = [a.config.name for a in agents]
        agent_descriptions = "\n".join(f"- {a.config.name}: {a.config.description}" for a in agents)
        valid_options = [*agent_names, "__end__"]
        supervisor_llm = self._llm.with_structured_output(_RouterDecision)

        async def supervisor_node(
            state: _WorkspaceState,
        ) -> Command[str]:
            messages = state["messages"]
            # Agent just responded — return to the user.
            if messages and isinstance(messages[-1], AIMessage):
                return Command(goto=END)

            if not agent_names:
                return Command(goto=END)

            system = SystemMessage(
                content=(
                    "You are a routing supervisor. Given the conversation so far, "
                    "pick the most suitable agent for the user's latest request.\n\n"
                    f"Available agents:\n{agent_descriptions}\n\n"
                    f"Respond with exactly one of: {', '.join(valid_options)}. "
                    "Use '__end__' only if no agent can handle the request."
                )
            )
            result = await supervisor_llm.ainvoke([system, *messages])
            decision: str = getattr(result, "next_agent", "__end__")
            if decision not in valid_options:
                decision = agent_names[0]
            if decision == "__end__":
                return Command(goto=END)
            return Command(
                goto=decision,
                update={"agent_used": decision},
            )

        def _make_agent_node(agent: Agent) -> Any:
            async def agent_node(state: _WorkspaceState) -> Command[str]:
                new_messages = await agent.run_with_context(list(state["messages"]))
                return Command(goto="supervisor", update={"messages": new_messages})

            agent_node.__name__ = agent.config.name
            return agent_node

        builder: StateGraph[_WorkspaceState, Any, Any] = StateGraph(_WorkspaceState)
        builder.add_node("supervisor", supervisor_node)
        for agent in agents:
            builder.add_node(agent.config.name, _make_agent_node(agent))
        builder.add_edge(START, "supervisor")

        return builder.compile(checkpointer=self._checkpointer)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        message: str,
        thread_id: str | None = None,
    ) -> tuple[str, str, str]:
        """Invoke the supervisor graph with a new user message.

        Args:
            message: User message text.
            thread_id: Conversation thread ID. A new UUID is generated if not
                provided.

        Returns:
            Tuple of ``(response_text, thread_id, agent_used)``.
        """
        if not self._agents:
            raise RuntimeError("No agents available in workspace supervisor.")

        if thread_id is None:
            thread_id = str(uuid.uuid4())

        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
        result: dict[str, Any] = await self._graph.ainvoke(
            {"messages": [HumanMessage(content=message)]},
            config=config,
        )
        messages: list[BaseMessage] = result.get("messages", [])
        last_ai = next(
            (m for m in reversed(messages) if isinstance(m, AIMessage)),
            None,
        )
        response = last_ai.content if last_ai is not None else ""
        if not isinstance(response, str):
            response = str(response)

        agent_used: str = result.get("agent_used", "")
        return response, thread_id, agent_used

    def rebuild(self, agents: list[Agent]) -> None:
        """Rebuild the supervisor graph with an updated list of agents.

        Called by ``Workspace`` whenever agents are added or removed.
        """
        self._agents = agents
        self._graph = self._build()
