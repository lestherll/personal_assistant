"""Functional test fixtures.

Overrides ``http_client`` to replace workspace supervisor graphs with mocks
so that functional tests never make real LLM API calls.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage


@pytest.fixture
async def http_client(live_server_url: str) -> AsyncIterator[httpx.AsyncClient]:
    """Pre-configured AsyncClient pointed at the live server.

    Overrides the root conftest fixture to patch workspace supervisor graphs
    and individual agent graphs with mocks so that no real LLM calls are made
    during functional tests.  Evaluation tests (``tests/evaluation/``) use the
    root fixture which does NOT apply this patch.
    """
    from api.main import app

    orchestrator = app.state.orchestrator
    for ws_name in orchestrator.list_workspaces():
        ws = orchestrator.get_workspace(ws_name)
        if ws is None:
            continue

        # Mock each agent's internal ReAct graph.
        for agent_name in ws.list_agents():
            agent = ws.get_agent(agent_name)
            if agent is None:
                continue
            mock_agent_graph = MagicMock()
            mock_agent_graph.ainvoke = AsyncMock(
                return_value={
                    "messages": [
                        HumanMessage(content="mock input"),
                        AIMessage(content=f"Mock reply from {agent_name}"),
                    ]
                }
            )

            def _make_astream(
                name: str,
            ) -> object:
                async def _fake_astream(
                    *args: object, **kwargs: object
                ) -> AsyncIterator[dict[str, list[object]]]:
                    yield {
                        "messages": [
                            HumanMessage(content="mock input"),
                            AIMessage(content=f"Mock stream reply from {name}"),
                        ]
                    }

                return _fake_astream

            mock_agent_graph.astream = _make_astream(agent_name)
            agent._graph = mock_agent_graph

        # Mock the workspace supervisor compiled graph.
        if ws._supervisor is not None:
            default_agent = ws.list_agents()[0] if ws.list_agents() else ""
            mock_supervisor_graph = MagicMock()
            mock_supervisor_graph.ainvoke = AsyncMock(
                return_value={
                    "messages": [
                        HumanMessage(content="mock input"),
                        AIMessage(content="Mock workspace response"),
                    ],
                    "agent_used": default_agent,
                }
            )
            ws._supervisor._graph = mock_supervisor_graph

    async with httpx.AsyncClient(base_url=live_server_url) as client:
        yield client
