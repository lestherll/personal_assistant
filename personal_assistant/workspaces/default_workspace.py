from personal_assistant.agents import DEFAULT_AGENTS
from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.core.workspace import Workspace, WorkspaceConfig
from personal_assistant.tools.example_tool import AgentInformationTool, EchoTool
from personal_assistant.tools.indeed_tool import IndeedJobSearchTool


def create_default_workspace(orchestrator: Orchestrator) -> Workspace:
    """Bootstrap a default workspace with a general-purpose assistant."""
    config = WorkspaceConfig(
        name="default",
        description="Default workspace — general-purpose assistant.",
    )
    workspace = orchestrator.create_workspace(config)

    workspace.add_agents(
        [create_agent(orchestrator.registry) for create_agent in DEFAULT_AGENTS.values()]
    )
    workspace.add_tool(EchoTool())
    workspace.add_tool(AgentInformationTool())

    # Wire career-specific tools to the CareerAgent only
    workspace.add_tool_to_agent("CareerAgent", IndeedJobSearchTool())

    return workspace
