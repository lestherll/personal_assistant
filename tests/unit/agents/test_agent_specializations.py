"""Unit tests for agent specialization classes."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from personal_assistant.agents import DEFAULT_AGENTS
from personal_assistant.agents.assistant_agent import AssistantAgent
from personal_assistant.agents.career_agent import CareerAgent
from personal_assistant.agents.coding_agent import PythonCodingAgent
from personal_assistant.agents.research_agent import GeneralResearchAgent
from personal_assistant.core.agent import Agent
from personal_assistant.providers.registry import ProviderRegistry
from tests.unit.conftest import make_mock_graph, make_mock_provider


@pytest.fixture
def mock_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(make_mock_provider("mock"), default=True)
    return registry


AGENT_CLASSES = [
    (AssistantAgent, "Assistant"),
    (CareerAgent, "CareerAgent"),
    (PythonCodingAgent, "PythonCodingAgent"),
    (GeneralResearchAgent, "GeneralResearchAgent"),
]


class TestAgentSpecializationCreate:
    @pytest.mark.parametrize("agent_cls, default_name", AGENT_CLASSES)
    def test_create_returns_correct_type(self, agent_cls, default_name, mock_registry):
        with patch("personal_assistant.core.agent.create_agent", return_value=make_mock_graph()):
            agent = agent_cls.create(mock_registry)
        assert isinstance(agent, agent_cls)

    @pytest.mark.parametrize("agent_cls, default_name", AGENT_CLASSES)
    def test_create_uses_default_name(self, agent_cls, default_name, mock_registry):
        with patch("personal_assistant.core.agent.create_agent", return_value=make_mock_graph()):
            agent = agent_cls.create(mock_registry)
        assert agent.config.name == default_name

    @pytest.mark.parametrize("agent_cls, default_name", AGENT_CLASSES)
    def test_create_accepts_custom_name(self, agent_cls, default_name, mock_registry):
        with patch("personal_assistant.core.agent.create_agent", return_value=make_mock_graph()):
            agent = agent_cls.create(mock_registry, name="CustomName")
        assert agent.config.name == "CustomName"

    @pytest.mark.parametrize("agent_cls, default_name", AGENT_CLASSES)
    def test_config_description_is_non_empty(self, agent_cls, default_name, mock_registry):
        with patch("personal_assistant.core.agent.create_agent", return_value=make_mock_graph()):
            agent = agent_cls.create(mock_registry)
        assert agent.config.description.strip() != ""

    @pytest.mark.parametrize("agent_cls, default_name", AGENT_CLASSES)
    def test_config_system_prompt_is_non_empty(self, agent_cls, default_name, mock_registry):
        with patch("personal_assistant.core.agent.create_agent", return_value=make_mock_graph()):
            agent = agent_cls.create(mock_registry)
        assert agent.config.system_prompt.strip() != ""


class TestDefaultAgentsDict:
    def test_dict_contains_four_keys(self):
        assert len(DEFAULT_AGENTS) == 4

    def test_all_callables_return_agent_instances(self, mock_registry):
        with patch("personal_assistant.core.agent.create_agent", return_value=make_mock_graph()):
            for create_fn in DEFAULT_AGENTS.values():
                agent = create_fn(mock_registry)
                assert isinstance(agent, Agent)
