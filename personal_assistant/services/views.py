from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentConfigView:
    name: str
    description: str
    system_prompt: str
    provider: str | None
    model: str | None
    allowed_tools: list[str]


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


@dataclass
class WorkspaceChatView:
    response: str
    thread_id: str
    agent_used: str
