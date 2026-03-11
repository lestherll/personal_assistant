from ..core.agent import Agent, AgentConfig
from ..providers.registry import ProviderRegistry


class AssistantAgent(Agent):
    """A general-purpose assistant agent for everyday tasks."""

    @classmethod
    def create(cls, registry: ProviderRegistry, name: str = "Assistant") -> "AssistantAgent":
        config = AgentConfig(
            name=name,
            description=(
                "A general-purpose assistant that handles a wide range of tasks: "
                "answering questions, summarising content, drafting text, and more."
            ),
            system_prompt=(
                "You are a helpful personal assistant. "
                "Help the user with questions, analysis, writing, and any task they bring you. "
                "Be concise, accurate, and proactive about asking for clarification when needed."
            ),
        )
        return cls(config, registry)
