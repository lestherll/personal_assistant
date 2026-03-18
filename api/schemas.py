from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from personal_assistant.persistence.repository import AgentParticipationView
from personal_assistant.services.views import (
    AgentView,
    ConversationView,
    UsageByAgentView,
    UsageSummaryView,
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
    allowed_tools: list[str] | None


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
    workspace_id: uuid.UUID
    user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    title: str | None = None

    @classmethod
    def from_view(cls, view: ConversationView) -> ConversationResponse:
        return cls(
            id=view.id,
            workspace_id=view.workspace_id,
            user_id=view.user_id,
            created_at=view.created_at,
            updated_at=view.updated_at,
            title=view.title,
        )


class RenameConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class AgentParticipationResponse(BaseModel):
    agent_id: uuid.UUID
    agent_name: str
    message_count: int

    @classmethod
    def from_view(cls, view: AgentParticipationView) -> AgentParticipationResponse:
        return cls(
            agent_id=view.agent_id,
            agent_name=view.agent_name,
            message_count=view.message_count,
        )


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    agent_id: uuid.UUID | None
    created_at: datetime


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


class UsageSummaryResponse(BaseModel):
    workspace: str
    provider: str | None
    model: str | None
    period_start: datetime
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float

    @classmethod
    def from_view(cls, view: UsageSummaryView) -> UsageSummaryResponse:
        return cls(**dataclasses.asdict(view))


class UsageByAgentResponse(BaseModel):
    workspace: str
    agent_id: uuid.UUID
    agent_name: str
    provider: str | None
    model: str | None
    period_start: datetime
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float

    @classmethod
    def from_view(cls, view: UsageByAgentView) -> UsageByAgentResponse:
        return cls(**dataclasses.asdict(view))


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


# ---------------------------------------------------------------------------
# Auth schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    created_at: datetime


class RegisterResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse


# ---------------------------------------------------------------------------
# API key schemas
# ---------------------------------------------------------------------------


class CreateAPIKeyRequest(BaseModel):
    name: str


class APIKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime


class CreateAPIKeyResponse(BaseModel):
    key: str
    api_key: APIKeyResponse
