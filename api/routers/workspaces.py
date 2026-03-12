from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from api.dependencies import get_workspace_service
from api.schemas import WorkspaceDetailResponse, WorkspaceResponse
from personal_assistant.services.schemas import (
    CreateWorkspaceRequest,
    UpdateWorkspaceRequest,
)
from personal_assistant.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

WorkspaceServiceDep = Annotated[WorkspaceService, Depends(get_workspace_service)]


@router.post("/", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(
    body: CreateWorkspaceRequest,
    service: WorkspaceServiceDep,
) -> WorkspaceResponse:
    view = service.create_workspace(
        name=body.name,
        description=body.description,
        metadata=body.metadata,
    )
    return WorkspaceResponse.from_view(view)


@router.get("/", response_model=list[WorkspaceResponse])
def list_workspaces(service: WorkspaceServiceDep) -> list[WorkspaceResponse]:
    return [WorkspaceResponse.from_view(v) for v in service.list_workspaces()]


@router.get("/{name}", response_model=WorkspaceDetailResponse)
def get_workspace(name: str, service: WorkspaceServiceDep) -> WorkspaceDetailResponse:
    view = service.get_workspace(name)
    return WorkspaceDetailResponse.from_view(view)


@router.patch("/{name}", response_model=WorkspaceResponse)
def update_workspace(
    name: str,
    body: UpdateWorkspaceRequest,
    service: WorkspaceServiceDep,
) -> WorkspaceResponse:
    view = service.update_workspace(
        name,
        description=body.description,
        metadata=body.metadata,
    )
    return WorkspaceResponse.from_view(view)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(name: str, service: WorkspaceServiceDep) -> None:
    service.delete_workspace(name)
