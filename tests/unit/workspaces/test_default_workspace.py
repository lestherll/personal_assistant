"""Unit tests for the default workspace factory."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.core.workspace import Workspace
from personal_assistant.providers.registry import ProviderRegistry
from personal_assistant.workspaces.default_workspace import create_default_workspace
from tests.unit.conftest import make_mock_graph, make_mock_provider


@pytest.fixture
def orchestrator() -> Orchestrator:
    registry = ProviderRegistry()
    registry.register(make_mock_provider("mock"), default=True)
    return Orchestrator(registry)


class TestCreateDefaultWorkspace:
    def test_returns_workspace_instance(self, orchestrator):
        with patch("personal_assistant.core.agent.create_agent", return_value=make_mock_graph()):
            ws = create_default_workspace(orchestrator)
        assert isinstance(ws, Workspace)

    def test_workspace_name_is_default(self, orchestrator):
        with patch("personal_assistant.core.agent.create_agent", return_value=make_mock_graph()):
            ws = create_default_workspace(orchestrator)
        assert ws.config.name == "default"

    def test_adds_four_agents(self, orchestrator):
        with patch("personal_assistant.core.agent.create_agent", return_value=make_mock_graph()):
            ws = create_default_workspace(orchestrator)
        assert len(ws.list_agents()) == 4

    def test_adds_echo_tool(self, orchestrator):
        with patch("personal_assistant.core.agent.create_agent", return_value=make_mock_graph()):
            ws = create_default_workspace(orchestrator)
        assert "echo" in ws.list_tools()

    def test_adds_agent_information_tool(self, orchestrator):
        with patch("personal_assistant.core.agent.create_agent", return_value=make_mock_graph()):
            ws = create_default_workspace(orchestrator)
        assert "agent_info" in ws.list_tools()
