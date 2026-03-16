from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AgentConfigView:
    name: str
    description: str
    system_prompt: str
    provider: str | None
    model: str | None
    allowed_tools: list[str] | None


@dataclass
class AgentView:
    config: AgentConfigView
    tools: list[str]
    llm_info: dict[str, str | None]


@dataclass
class WorkspaceView:
    name: str
    description: str
    metadata: dict[str, Any] = field(default_factory=lambda: {})
    agents: list[str] = field(default_factory=lambda: [])
    tools: list[str] = field(default_factory=lambda: [])


@dataclass
class WorkspaceDetailView:
    name: str
    description: str
    metadata: dict[str, Any] = field(default_factory=lambda: {})
    agents: list[AgentView] = field(default_factory=lambda: [])
    tools: list[str] = field(default_factory=lambda: [])


@dataclass(frozen=True)
class ConversationView:
    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


@dataclass
class WorkspaceChatView:
    response: str
    conversation_id: str
    agent_used: str


@dataclass(frozen=True)
class MessageView:
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    agent_id: uuid.UUID | None
    created_at: datetime


@dataclass
class ProviderView:
    name: str
    default_model: str


@dataclass
class ProviderModelsView:
    name: str
    models: list[str]
