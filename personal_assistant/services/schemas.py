from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateWorkspaceRequest(BaseModel):
    name: str
    description: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateWorkspaceRequest(BaseModel):
    description: str | None = None
    metadata: dict[str, Any] | None = None


class CreateAgentRequest(BaseModel):
    name: str
    description: str
    system_prompt: str
    provider: str | None = None
    model: str | None = None
    allowed_tools: list[str] = Field(default_factory=list)


class UpdateAgentRequest(BaseModel):
    description: str | None = None
    system_prompt: str | None = None
    provider: str | None = None
    model: str | None = None
    allowed_tools: list[str] | None = None


class ChatRequest(BaseModel):
    message: str
