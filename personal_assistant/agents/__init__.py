from personal_assistant.agents.assistant_agent import AssistantAgent
from personal_assistant.agents.career_agent import CareerAgent
from personal_assistant.agents.coding_agent import PythonCodingAgent
from personal_assistant.agents.research_agent import GeneralResearchAgent

__all__ = [
    AssistantAgent,
    CareerAgent,
    PythonCodingAgent,
    GeneralResearchAgent,
]

DEFAULT_AGENTS = {
    "assistant": AssistantAgent,
    "career": CareerAgent,
    "coding": PythonCodingAgent,
    "research": GeneralResearchAgent,
}
