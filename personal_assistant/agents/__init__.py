from personal_assistant.agents.assistant_agent import AssistantAgent
from personal_assistant.agents.career_agent import CareerAgent
from personal_assistant.agents.coding_agent import PythonCodingAgent
from personal_assistant.agents.research_agent import GeneralResearchAgent
from personal_assistant.core.agent import Agent

DEFAULT_AGENTS: dict[str, type[Agent]] = {
    "assistant": AssistantAgent,
    "career": CareerAgent,
    "coding": PythonCodingAgent,
    "research": GeneralResearchAgent,
}
