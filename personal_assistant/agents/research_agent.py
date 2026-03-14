from personal_assistant.core.agent import Agent, AgentConfig
from personal_assistant.providers.registry import ProviderRegistry


class GeneralResearchAgent(Agent):
    """
    An agent specialised in research tasks, like summarising articles,
    extracting key information, and answering questions based on provided content.
    """

    @classmethod
    def create(
        cls, registry: ProviderRegistry, name: str = "GeneralResearchAgent"
    ) -> "GeneralResearchAgent":
        config = AgentConfig(
            name=name,
            description=(
                "A general research assistant that helps with summarising articles, "
                "extracting key information, and answering questions based on provided content. "
                "Be thorough, accurate, and proactive about asking for clarification when needed."
            ),
            system_prompt=(
                "You are a general research assistant. "
                "Help the user summarise articles, extract key information, and "
                "answer questions based on provided content. "
                "Be thorough and accurate in your responses."
            ),
        )
        return cls(config, registry)
