from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentUserDep, get_db_session, get_workspace_service
from api.routers.params import WorkspaceName
from api.schemas import WorkspaceChatResponse, WorkspaceDetailResponse, WorkspaceResponse
from personal_assistant.services.schemas import (
    CreateWorkspaceRequest,
    UpdateWorkspaceRequest,
    WorkspaceChatRequest,
)
from personal_assistant.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

WorkspaceServiceDep = Annotated[WorkspaceService, Depends(get_workspace_service)]
DbSessionDep = Annotated[AsyncSession | None, Depends(get_db_session)]


@router.post("/", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(
    body: CreateWorkspaceRequest,
    service: WorkspaceServiceDep,
    _user: CurrentUserDep,
) -> WorkspaceResponse:
    view = service.create_workspace(
        name=body.name,
        description=body.description,
        metadata=body.metadata,
    )
    return WorkspaceResponse.from_view(view)


@router.get("/", response_model=list[WorkspaceResponse])
def list_workspaces(service: WorkspaceServiceDep, _user: CurrentUserDep) -> list[WorkspaceResponse]:
    return [WorkspaceResponse.from_view(v) for v in service.list_workspaces()]


@router.get("/{name}", response_model=WorkspaceDetailResponse)
def get_workspace(
    name: WorkspaceName, service: WorkspaceServiceDep, _user: CurrentUserDep
) -> WorkspaceDetailResponse:
    view = service.get_workspace(name)
    return WorkspaceDetailResponse.from_view(view)


@router.patch("/{name}", response_model=WorkspaceResponse)
def update_workspace(
    name: WorkspaceName,
    body: UpdateWorkspaceRequest,
    service: WorkspaceServiceDep,
    _user: CurrentUserDep,
) -> WorkspaceResponse:
    view = service.update_workspace(
        name,
        description=body.description,
        metadata=body.metadata,
    )
    return WorkspaceResponse.from_view(view)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(
    name: WorkspaceName, service: WorkspaceServiceDep, _user: CurrentUserDep
) -> None:
    service.delete_workspace(name)


@router.post("/{name}/chat", response_model=WorkspaceChatResponse)
async def workspace_chat(
    name: WorkspaceName,
    body: WorkspaceChatRequest,
    service: WorkspaceServiceDep,
    db: DbSessionDep,
    _user: CurrentUserDep,
) -> WorkspaceChatResponse:
    view = await service.chat(
        workspace_name=name,
        message=body.message,
        conversation_id=body.conversation_id,
        agent_name=body.agent_name,
        provider=body.provider,
        model=body.model,
        session=db,
    )
    return WorkspaceChatResponse(
        response=view.response,
        conversation_id=view.conversation_id,
        agent_used=view.agent_used,
    )


@router.post("/{name}/chat/stream")
async def workspace_chat_stream(
    name: WorkspaceName,
    body: WorkspaceChatRequest,
    service: WorkspaceServiceDep,
    db: DbSessionDep,
    _user: CurrentUserDep,
) -> StreamingResponse:
    token_iter, conversation_id, agent_used = await service.stream_chat(
        workspace_name=name,
        message=body.message,
        conversation_id=body.conversation_id,
        agent_name=body.agent_name,
        provider=body.provider,
        model=body.model,
        session=db,
    )

    async def event_generator() -> AsyncIterator[str]:
        async for token in token_iter:
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "X-Conversation-Id": conversation_id,
            "X-Agent-Used": agent_used,
        },
    )
