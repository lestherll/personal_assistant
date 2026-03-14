from collections.abc import Callable

from personal_assistant.agents.assistant_agent import AssistantAgent
from personal_assistant.agents.career_agent import CareerAgent
from personal_assistant.agents.coding_agent import PythonCodingAgent
from personal_assistant.agents.research_agent import GeneralResearchAgent
from personal_assistant.core.agent import Agent
from personal_assistant.providers.registry import ProviderRegistry

DEFAULT_AGENTS: dict[str, Callable[[ProviderRegistry], Agent]] = {
    "assistant": AssistantAgent.create,
    "career": CareerAgent.create,
    "coding": PythonCodingAgent.create,
    "research": GeneralResearchAgent.create,
}
