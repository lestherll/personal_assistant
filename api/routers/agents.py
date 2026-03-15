from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentUserDep, get_agent_service, get_db_session
from api.routers.params import AgentName, WorkspaceName
from api.schemas import AgentResponse, ChatResponse, ConversationResponse
from personal_assistant.services.agent_service import AgentService
from personal_assistant.services.schemas import (
    ChatRequest,
    CreateAgentRequest,
    UpdateAgentRequest,
)

router = APIRouter(
    prefix="/workspaces/{workspace_name}/agents",
    tags=["agents"],
)

AgentServiceDep = Annotated[AgentService, Depends(get_agent_service)]
DbSessionDep = Annotated[AsyncSession | None, Depends(get_db_session)]


@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    workspace_name: WorkspaceName,
    body: CreateAgentRequest,
    service: AgentServiceDep,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> AgentResponse:
    view = await service.create_agent(
        current_user.id,
        workspace_name=workspace_name,
        name=body.name,
        description=body.description,
        system_prompt=body.system_prompt,
        provider=body.provider,
        model=body.model,
        allowed_tools=body.allowed_tools,
        session=db,
    )
    return AgentResponse.from_view(view)


@router.get("/", response_model=list[AgentResponse])
async def list_agents(
    workspace_name: WorkspaceName,
    service: AgentServiceDep,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> list[AgentResponse]:
    views = await service.list_agents(current_user.id, workspace_name, session=db)
    return [AgentResponse.from_view(v) for v in views]


@router.get("/{agent_name}", response_model=AgentResponse)
async def get_agent(
    workspace_name: WorkspaceName,
    agent_name: AgentName,
    service: AgentServiceDep,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> AgentResponse:
    view = await service.get_agent(current_user.id, workspace_name, agent_name, session=db)
    return AgentResponse.from_view(view)


@router.patch("/{agent_name}", response_model=AgentResponse)
async def update_agent(
    workspace_name: WorkspaceName,
    agent_name: AgentName,
    body: UpdateAgentRequest,
    service: AgentServiceDep,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> AgentResponse:
    view = await service.update_agent(
        current_user.id,
        workspace_name,
        agent_name,
        description=body.description,
        system_prompt=body.system_prompt,
        provider=body.provider,
        model=body.model,
        allowed_tools=body.allowed_tools,
        session=db,
    )
    return AgentResponse.from_view(view)


@router.delete("/{agent_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    workspace_name: WorkspaceName,
    agent_name: AgentName,
    service: AgentServiceDep,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> None:
    await service.delete_agent(current_user.id, workspace_name, agent_name, session=db)


@router.post("/{agent_name}/chat", response_model=ChatResponse)
async def chat(
    workspace_name: WorkspaceName,
    agent_name: AgentName,
    body: ChatRequest,
    service: AgentServiceDep,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> ChatResponse:
    reply, conv_id = await service.run_agent(
        current_user.id,
        workspace_name,
        agent_name,
        body.message,
        conversation_id=body.conversation_id,
        session=db,
    )
    return ChatResponse(reply=reply, conversation_id=conv_id)


@router.post("/{agent_name}/chat/stream")
async def chat_stream(
    workspace_name: WorkspaceName,
    agent_name: AgentName,
    body: ChatRequest,
    service: AgentServiceDep,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> StreamingResponse:
    tokens, conv_id = await service.stream_agent(
        current_user.id,
        workspace_name,
        agent_name,
        body.message,
        conversation_id=body.conversation_id,
        session=db,
    )

    async def event_generator() -> AsyncIterator[str]:
        async for token in tokens:
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"X-Conversation-Id": str(conv_id)},
    )


@router.get("/{agent_name}/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    workspace_name: WorkspaceName,
    agent_name: AgentName,
    service: AgentServiceDep,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> list[ConversationResponse]:
    if db is None:
        return []
    views = await service.list_conversations(current_user.id, workspace_name, db)
    return [ConversationResponse.from_view(v) for v in views]


@router.delete(
    "/{agent_name}/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    workspace_name: WorkspaceName,
    agent_name: AgentName,
    conversation_id: uuid.UUID,
    service: AgentServiceDep,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> None:
    if db is None:
        from personal_assistant.services.exceptions import NotFoundError

        raise NotFoundError("conversation", str(conversation_id))
    await service.delete_conversation(current_user.id, workspace_name, conversation_id, db)
