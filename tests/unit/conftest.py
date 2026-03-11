"""Shared fixtures for unit tests."""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from personal_assistant.core.agent import Agent, AgentConfig
from personal_assistant.providers.base import AIProvider

# ---------------------------------------------------------------------------
# Provider / registry helpers
# ---------------------------------------------------------------------------


def make_mock_provider(name: str = "mock") -> AIProvider:
    provider = MagicMock(spec=AIProvider)
    provider.name = name
    provider.default_model = "mock-model"
    provider.get_model.return_value = MagicMock()
    return provider


@pytest.fixture
def mock_provider():
    return make_mock_provider()


@pytest.fixture
def mock_registry(mock_provider):
    from personal_assistant.providers.registry import ProviderRegistry

    registry = ProviderRegistry()
    registry.register(mock_provider, default=True)
    return registry


# ---------------------------------------------------------------------------
# Agent helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def agent_config():
    return AgentConfig(
        name="TestAgent",
        description="A test agent",
        system_prompt="You are a test assistant.",
    )


def make_mock_graph(response: str = "Test response"):
    graph = MagicMock()
    graph.invoke.return_value = {
        "messages": [
            HumanMessage(content="Hello"),
            AIMessage(content=response),
        ]
    }
    graph.stream.return_value = iter(
        [{"messages": [HumanMessage(content="Hello"), AIMessage(content=response)]}]
    )
    return graph


@pytest.fixture
def mock_graph():
    return make_mock_graph()


@pytest.fixture
def agent(agent_config, mock_registry, mock_graph):
    with patch("personal_assistant.core.agent.create_react_agent", return_value=mock_graph):
        return Agent(agent_config, mock_registry)
