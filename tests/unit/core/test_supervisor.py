"""Unit tests for WorkspaceSupervisor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from personal_assistant.core.agent import Agent, AgentConfig
from personal_assistant.core.supervisor import WorkspaceSupervisor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_agent(name: str = "TestAgent", description: str = "A test agent") -> Agent:
    agent = MagicMock(spec=Agent)
    agent.config = AgentConfig(
        name=name,
        description=description,
        system_prompt="You are a test assistant.",
    )
    agent.llm = MagicMock()
    return agent


def make_mock_llm() -> MagicMock:
    llm = MagicMock()
    router_llm = MagicMock()
    router_llm.ainvoke = AsyncMock()
    llm.with_structured_output.return_value = router_llm
    return llm


# ---------------------------------------------------------------------------
# Graph structure tests
# ---------------------------------------------------------------------------


class TestWorkspaceSupervisorBuild:
    def test_supervisor_node_present(self) -> None:
        agent = make_mock_agent("Alpha")
        llm = make_mock_llm()
        supervisor = WorkspaceSupervisor([agent], llm)
        assert "supervisor" in supervisor._graph.get_graph().nodes

    def test_agent_nodes_present(self) -> None:
        alpha = make_mock_agent("Alpha")
        beta = make_mock_agent("Beta")
        llm = make_mock_llm()
        supervisor = WorkspaceSupervisor([alpha, beta], llm)
        nodes = supervisor._graph.get_graph().nodes
        assert "Alpha" in nodes
        assert "Beta" in nodes

    def test_rebuild_updates_agent_nodes(self) -> None:
        alpha = make_mock_agent("Alpha")
        llm = make_mock_llm()
        supervisor = WorkspaceSupervisor([alpha], llm)
        assert "Alpha" in supervisor._graph.get_graph().nodes
        assert "Beta" not in supervisor._graph.get_graph().nodes

        beta = make_mock_agent("Beta")
        supervisor.rebuild([alpha, beta])
        assert "Alpha" in supervisor._graph.get_graph().nodes
        assert "Beta" in supervisor._graph.get_graph().nodes

    def test_rebuild_with_empty_agents(self) -> None:
        agent = make_mock_agent("Alpha")
        llm = make_mock_llm()
        supervisor = WorkspaceSupervisor([agent], llm)
        # Rebuild with no agents — should still produce a valid graph
        supervisor.rebuild([])
        assert supervisor._graph is not None


# ---------------------------------------------------------------------------
# run() tests
# ---------------------------------------------------------------------------


class TestWorkspaceSupervisorRun:
    @pytest.mark.asyncio
    async def test_run_generates_thread_id_when_none(self) -> None:
        agent = make_mock_agent("Alpha")
        llm = make_mock_llm()

        # Mock the compiled graph so we don't hit a real LLM
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "messages": [
                    HumanMessage(content="hi"),
                    AIMessage(content="hello"),
                ],
                "agent_used": "Alpha",
            }
        )

        supervisor = WorkspaceSupervisor([agent], llm)
        supervisor._graph = mock_graph

        _, thread_id, _ = await supervisor.run("hi")
        assert thread_id is not None
        assert len(thread_id) > 0

    @pytest.mark.asyncio
    async def test_run_preserves_provided_thread_id(self) -> None:
        agent = make_mock_agent("Alpha")
        llm = make_mock_llm()

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "messages": [
                    HumanMessage(content="hi"),
                    AIMessage(content="hello"),
                ],
                "agent_used": "Alpha",
            }
        )

        supervisor = WorkspaceSupervisor([agent], llm)
        supervisor._graph = mock_graph

        _, returned_tid, _ = await supervisor.run("hi", thread_id="my-thread")
        assert returned_tid == "my-thread"

    @pytest.mark.asyncio
    async def test_run_returns_agent_used(self) -> None:
        agent = make_mock_agent("Alpha")
        llm = make_mock_llm()

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "messages": [
                    HumanMessage(content="hi"),
                    AIMessage(content="hello from Alpha"),
                ],
                "agent_used": "Alpha",
            }
        )

        supervisor = WorkspaceSupervisor([agent], llm)
        supervisor._graph = mock_graph

        response, _, agent_used = await supervisor.run("hi", thread_id="t1")
        assert response == "hello from Alpha"
        assert agent_used == "Alpha"

    @pytest.mark.asyncio
    async def test_run_raises_when_no_agents(self) -> None:
        llm = make_mock_llm()
        supervisor = WorkspaceSupervisor([], llm)
        with pytest.raises(RuntimeError, match="No agents"):
            await supervisor.run("hi")
