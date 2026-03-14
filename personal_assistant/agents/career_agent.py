from personal_assistant.core.agent import Agent, AgentConfig
from personal_assistant.providers.registry import ProviderRegistry


class CareerAgent(Agent):
    """An agent specialised in career development tasks like resume review and interview prep."""

    @classmethod
    def create(cls, registry: ProviderRegistry, name: str = "CareerAgent") -> "CareerAgent":
        config = AgentConfig(
            name=name,
            description=(
                "A career development assistant that helps with resume/cv review, "
                "cover letter writing, interview preparation, and job search strategies."
            ),
            system_prompt=(
                "You are a career development assistant. "
                "Help the user improve their resume and cover letters, "
                "prepare for interviews, and provide guidance on job search strategies. "
                "Be constructive, encouraging, and proactive about asking for clarification "
                "when needed."
            ),
        )
        return cls(config, registry)
