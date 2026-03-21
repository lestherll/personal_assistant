from __future__ import annotations

import enum
import uuid
from typing import Any

from pydantic import BaseModel, Field


class TitleMode(enum.StrEnum):
    """Strategy for generating a conversation title on the first turn."""

    LLM = "llm"
    FIRST_20_WORDS = "first_20_words"
    UNTITLED = "untitled"
    CUSTOM = "custom"


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
    allowed_tools: list[str] | None = None


class UpdateAgentRequest(BaseModel):
    description: str | None = None
    system_prompt: str | None = None
    provider: str | None = None
    model: str | None = None
    allowed_tools: list[str] | None = None


class ChatRequest(BaseModel):
    message: str = Field(examples=["Hello, how are you?"])
    conversation_id: uuid.UUID | None = None  # Omit to start a new conversation
    title_mode: TitleMode = TitleMode.LLM
    title: str | None = None  # Required when title_mode == "custom"


class ResetRequest(BaseModel):
    conversation_id: uuid.UUID | None = None  # UUID of the conversation to reset


class WorkspaceChatRequest(BaseModel):
    message: str = Field(examples=["Hello, how are you?"])
    conversation_id: str | None = None  # Omit to start a new conversation
    agent_name: str | None = None  # Skip supervisor, target a specific agent
    provider: str | None = None  # Override provider (requires agent_name)
    model: str | None = None  # Override model (requires agent_name)
    title_mode: TitleMode = TitleMode.LLM
    title: str | None = None  # Required when title_mode == "custom"
