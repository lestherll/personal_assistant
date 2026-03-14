"""Shared fixtures for unit tests."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from personal_assistant.core.agent import Agent, AgentConfig
from personal_assistant.providers.base import AIProvider
from personal_assistant.providers.registry import ProviderRegistry

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
def mock_provider() -> AIProvider:
    return make_mock_provider()


@pytest.fixture
def mock_registry(mock_provider: AIProvider) -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(mock_provider, default=True)
    return registry


# ---------------------------------------------------------------------------
# Agent helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def agent_config() -> AgentConfig:
    return AgentConfig(
        name="TestAgent",
        description="A test agent",
        system_prompt="You are a test assistant.",
    )


def make_mock_graph(response: str = "Test response") -> MagicMock:
    messages = [HumanMessage(content="Hello"), AIMessage(content=response)]
    graph = MagicMock()

    # Sync (kept for tests that inspect call history directly)
    graph.invoke.return_value = {"messages": messages}
    graph.stream.return_value = iter([{"messages": messages}])

    # Async — used by Agent.run() and Agent.stream()
    graph.ainvoke = AsyncMock(return_value={"messages": messages})

    async def _astream(
        *args: object, **kwargs: object
    ) -> AsyncGenerator[dict[str, list[HumanMessage | AIMessage]]]:
        yield {"messages": messages}

    graph.astream = _astream
    return graph


@pytest.fixture
def mock_graph() -> MagicMock:
    return make_mock_graph()


@pytest.fixture
def agent(
    agent_config: AgentConfig, mock_registry: ProviderRegistry, mock_graph: MagicMock
) -> Agent:
    with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
        return Agent(agent_config, mock_registry)
