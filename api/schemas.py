from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from personal_assistant.services.views import (
    AgentView,
    ConversationView,
    WorkspaceDetailView,
    WorkspaceView,
)


class AgentConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str
    system_prompt: str
    provider: str | None
    model: str | None
    allowed_tools: list[str]


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    config: AgentConfigResponse
    tools: list[str]
    llm_info: dict[str, str | None]

    @classmethod
    def from_view(cls, view: AgentView) -> AgentResponse:
        return cls(
            config=AgentConfigResponse(**dataclasses.asdict(view.config)),
            tools=view.tools,
            llm_info=view.llm_info,
        )


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str
    metadata: dict[str, Any]
    agents: list[str]
    tools: list[str]

    @classmethod
    def from_view(cls, view: WorkspaceView) -> WorkspaceResponse:
        return cls(**dataclasses.asdict(view))


class WorkspaceDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str
    metadata: dict[str, Any]
    agents: list[AgentResponse]
    tools: list[str]

    @classmethod
    def from_view(cls, view: WorkspaceDetailView) -> WorkspaceDetailResponse:
        return cls(
            name=view.name,
            description=view.description,
            metadata=view.metadata,
            agents=[AgentResponse.from_view(a) for a in view.agents],
            tools=view.tools,
        )


class ConversationResponse(BaseModel):
    id: uuid.UUID
    agent_name: str
    workspace_name: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_view(cls, view: ConversationView) -> ConversationResponse:
        return cls(
            id=view.id,
            agent_name=view.agent_name,
            workspace_name=view.workspace_name,
            created_at=view.created_at,
            updated_at=view.updated_at,
        )


class ChatResponse(BaseModel):
    reply: str
    conversation_id: uuid.UUID  # always returned


class WorkspaceChatResponse(BaseModel):
    response: str
    conversation_id: str
    agent_used: str


class ProviderResponse(BaseModel):
    name: str
    default_model: str


class ProviderModelsResponse(BaseModel):
    name: str
    models: list[str]


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
