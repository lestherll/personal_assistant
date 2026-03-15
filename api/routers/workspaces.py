from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import (
    CurrentUserDep,
    get_agent_service,
    get_db_session,
    get_workspace_service,
)
from api.routers.params import WorkspaceName
from api.schemas import (
    ConversationResponse,
    WorkspaceChatResponse,
    WorkspaceDetailResponse,
    WorkspaceResponse,
)
from personal_assistant.services.agent_service import AgentService
from personal_assistant.services.schemas import (
    CreateWorkspaceRequest,
    UpdateWorkspaceRequest,
    WorkspaceChatRequest,
)
from personal_assistant.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

WorkspaceServiceDep = Annotated[WorkspaceService, Depends(get_workspace_service)]
AgentServiceDep = Annotated[AgentService, Depends(get_agent_service)]
DbSessionDep = Annotated[AsyncSession | None, Depends(get_db_session)]


@router.post("/", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    body: CreateWorkspaceRequest,
    service: WorkspaceServiceDep,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> WorkspaceResponse:
    view = await service.create_workspace(
        current_user.id,
        name=body.name,
        description=body.description,
        metadata=body.metadata,
        session=db,
    )
    return WorkspaceResponse.from_view(view)


@router.get("/", response_model=list[WorkspaceResponse])
async def list_workspaces(
    service: WorkspaceServiceDep,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> list[WorkspaceResponse]:
    views = await service.list_workspaces(current_user.id, session=db)
    return [WorkspaceResponse.from_view(v) for v in views]


@router.get("/{name}", response_model=WorkspaceDetailResponse)
async def get_workspace(
    name: WorkspaceName,
    service: WorkspaceServiceDep,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> WorkspaceDetailResponse:
    view = await service.get_workspace(current_user.id, name, session=db)
    return WorkspaceDetailResponse.from_view(view)


@router.patch("/{name}", response_model=WorkspaceResponse)
async def update_workspace(
    name: WorkspaceName,
    body: UpdateWorkspaceRequest,
    service: WorkspaceServiceDep,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> WorkspaceResponse:
    view = await service.update_workspace(
        current_user.id,
        name,
        description=body.description,
        session=db,
    )
    return WorkspaceResponse.from_view(view)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    name: WorkspaceName,
    service: WorkspaceServiceDep,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> None:
    await service.delete_workspace(current_user.id, name, session=db)


@router.post("/{name}/chat", response_model=WorkspaceChatResponse)
async def workspace_chat(
    name: WorkspaceName,
    body: WorkspaceChatRequest,
    service: WorkspaceServiceDep,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> WorkspaceChatResponse:
    view = await service.chat(
        current_user.id,
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
    current_user: CurrentUserDep,
) -> StreamingResponse:
    token_iter, conversation_id, agent_used = await service.stream_chat(
        current_user.id,
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


@router.get("/{name}/conversations", response_model=list[ConversationResponse])
async def list_workspace_conversations(
    name: WorkspaceName,
    agent_service: AgentServiceDep,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> list[ConversationResponse]:
    if db is None:
        return []
    views = await agent_service.list_conversations(current_user.id, name, db)
    return [ConversationResponse.from_view(v) for v in views]
