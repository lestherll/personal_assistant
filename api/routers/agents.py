from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from api.dependencies import get_agent_service
from api.schemas import AgentResponse
from personal_assistant.services.agent_service import AgentService
from personal_assistant.services.schemas import CreateAgentRequest, UpdateAgentRequest

router = APIRouter(
    prefix="/workspaces/{workspace_name}/agents",
    tags=["agents"],
)

AgentServiceDep = Annotated[AgentService, Depends(get_agent_service)]


@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent(
    workspace_name: str,
    body: CreateAgentRequest,
    service: AgentServiceDep,
) -> AgentResponse:
    view = service.create_agent(
        workspace_name=workspace_name,
        name=body.name,
        description=body.description,
        system_prompt=body.system_prompt,
        provider=body.provider,
        model=body.model,
        allowed_tools=body.allowed_tools,
    )
    return AgentResponse.from_view(view)


@router.get("/", response_model=list[AgentResponse])
def list_agents(workspace_name: str, service: AgentServiceDep) -> list[AgentResponse]:
    return [AgentResponse.from_view(v) for v in service.list_agents(workspace_name)]


@router.get("/{agent_name}", response_model=AgentResponse)
def get_agent(
    workspace_name: str, agent_name: str, service: AgentServiceDep
) -> AgentResponse:
    view = service.get_agent(workspace_name, agent_name)
    return AgentResponse.from_view(view)


@router.patch("/{agent_name}", response_model=AgentResponse)
def update_agent(
    workspace_name: str,
    agent_name: str,
    body: UpdateAgentRequest,
    service: AgentServiceDep,
) -> AgentResponse:
    view = service.update_agent(
        workspace_name,
        agent_name,
        description=body.description,
        system_prompt=body.system_prompt,
        provider=body.provider,
        model=body.model,
        allowed_tools=body.allowed_tools,
    )
    return AgentResponse.from_view(view)


@router.delete("/{agent_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(
    workspace_name: str, agent_name: str, service: AgentServiceDep
) -> None:
    service.delete_agent(workspace_name, agent_name)
