from personal_assistant.core.agent import Agent, AgentConfig
from personal_assistant.providers.registry import ProviderRegistry


class PythonCodingAgent(Agent):
    """
    An agent specialised in Python coding tasks,
    like writing functions, debugging, and code review.
    """

    @classmethod
    def create(
        cls, registry: ProviderRegistry, name: str = "PythonCodingAgent"
    ) -> "PythonCodingAgent":
        config = AgentConfig(
            name=name,
            description=(
                "A Python coding assistant that helps with writing functions, debugging code, "
                "and providing code reviews using the best practices and modern Python features. "
                "Be precise, provide clear explanations, and ask for clarification when needed."
            ),
            system_prompt=(
                "You are a Python coding assistant. "
                "Help the user write Python code, debug issues, and review their code. "
                "Provide clear explanations and be proactive about asking "
                "for clarification when needed."
            ),
        )
        return cls(config, registry)
