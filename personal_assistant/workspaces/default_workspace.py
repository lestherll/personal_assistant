from personal_assistant.agents.assistant_agent import AssistantAgent
from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.core.workspace import Workspace, WorkspaceConfig
from personal_assistant.tools.example_tool import EchoTool


def create_default_workspace(orchestrator: Orchestrator) -> Workspace:
    """Bootstrap a default workspace with a general-purpose assistant."""
    config = WorkspaceConfig(
        name="default",
        description="Default workspace — general-purpose assistant.",
    )
    workspace = orchestrator.create_workspace(config)

    workspace.add_agent(AssistantAgent.create(orchestrator.registry))
    workspace.add_tool(EchoTool())

    return workspace
