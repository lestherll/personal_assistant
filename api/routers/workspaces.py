from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import (
    CurrentUserDep,
    get_agent_service,
    get_db_session,
    get_workspace_service,
    rate_limit_chat,
)
from api.routers.params import PaginationLimit, PaginationSkip, WorkspaceName
from api.schemas import (
    AgentParticipationResponse,
    ConversationResponse,
    MessageResponse,
    RenameConversationRequest,
    WorkspaceChatResponse,
    WorkspaceDetailResponse,
    WorkspaceResponse,
)
from api.streaming import sse_event_generator
from personal_assistant.services.agent_service import AgentService
from personal_assistant.services.exceptions import ServiceValidationError
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


def _require_session(session: AsyncSession | None) -> AsyncSession:
    if session is None:
        raise ServiceValidationError(
            "Database not configured. Set DATABASE_URL to enable conversation renaming."
        )
    return session


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
    skip: PaginationSkip = 0,
    limit: PaginationLimit = 50,
) -> list[WorkspaceResponse]:
    views = await service.list_workspaces(current_user.id, skip=skip, limit=limit, session=db)
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


@router.post(
    "/{name}/chat", response_model=WorkspaceChatResponse, dependencies=[Depends(rate_limit_chat)]
)
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


@router.post("/{name}/chat/stream", dependencies=[Depends(rate_limit_chat)])
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

    return StreamingResponse(
        sse_event_generator(token_iter),
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
    skip: PaginationSkip = 0,
    limit: PaginationLimit = 50,
    q: Annotated[
        str | None, Query(description="Filter conversations by title (case-insensitive).")
    ] = None,
) -> list[ConversationResponse]:
    if db is None:
        return []
    views = await agent_service.list_conversations(
        current_user.id, name, db, skip=skip, limit=limit, search_term=q
    )
    return [ConversationResponse.from_view(v) for v in views]


@router.get(
    "/{name}/conversations/{conversation_id}/agents",
    response_model=list[AgentParticipationResponse],
)
async def list_conversation_agents(
    name: WorkspaceName,
    conversation_id: uuid.UUID,
    agent_service: AgentServiceDep,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> list[AgentParticipationResponse]:
    """Return which agents contributed messages to a conversation, with message counts."""
    if db is None:
        return []
    views = await agent_service.list_agent_participation(current_user.id, name, conversation_id, db)
    return [AgentParticipationResponse.from_view(v) for v in views]


@router.get(
    "/{name}/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
async def list_conversation_messages(
    name: WorkspaceName,
    conversation_id: uuid.UUID,
    agent_service: AgentServiceDep,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> list[MessageResponse]:
    """Return all messages in a conversation, ordered by sequence."""
    if db is None:
        return []
    views = await agent_service.get_conversation_messages(
        current_user.id, name, conversation_id, db
    )
    return [
        MessageResponse(
            id=v.id,
            conversation_id=v.conversation_id,
            role=v.role,
            content=v.content,
            agent_id=v.agent_id,
            created_at=v.created_at,
        )
        for v in views
    ]


@router.patch("/{name}/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def rename_conversation(
    name: WorkspaceName,
    conversation_id: uuid.UUID,
    body: RenameConversationRequest,
    user: CurrentUserDep,
    db: DbSessionDep,
    agent_service: AgentServiceDep,
) -> None:
    session = _require_session(db)
    await agent_service.rename_conversation(user.id, name, conversation_id, body.title, session)
