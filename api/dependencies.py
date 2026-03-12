from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request

from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.services.agent_service import AgentService
from personal_assistant.services.workspace_service import WorkspaceService


def get_orchestrator(request: Request) -> Orchestrator:
    """Return the application-scoped Orchestrator stored on app.state."""
    return cast(Orchestrator, request.app.state.orchestrator)


def get_workspace_service(
    orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
) -> WorkspaceService:
    """Return a request-scoped WorkspaceService wrapping the orchestrator."""
    return WorkspaceService(orchestrator)


def get_agent_service(
    orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
) -> AgentService:
    """Return a request-scoped AgentService wrapping the orchestrator."""
    return AgentService(orchestrator)
