"""Unit tests for api.schemas — round-trip conversion from service views."""

from __future__ import annotations

from api.schemas import (
    AgentConfigResponse,
    AgentResponse,
    ChatResponse,
    ErrorResponse,
    WorkspaceDetailResponse,
    WorkspaceResponse,
)
from personal_assistant.services.views import (
    AgentConfigView,
    AgentView,
    WorkspaceDetailView,
    WorkspaceView,
)


def _agent_config_view(**overrides: object) -> AgentConfigView:
    defaults: dict[str, object] = {
        "name": "TestAgent",
        "description": "desc",
        "system_prompt": "You are helpful.",
        "provider": "ollama",
        "model": "qwen2.5:14b",
        "allowed_tools": ["echo"],
    }
    defaults.update(overrides)
    return AgentConfigView(**defaults)  # type: ignore[arg-type]


def _agent_view(**overrides: object) -> AgentView:
    return AgentView(
        config=_agent_config_view(),
        tools=["echo"],
        llm_info={"provider": "ollama", "model": "qwen2.5:14b", "source": "registry"},
        **overrides,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# AgentConfigResponse
# ---------------------------------------------------------------------------


def test_agent_config_response_fields():
    view = _agent_config_view()
    resp = AgentConfigResponse(**view.__dict__)

    assert resp.name == view.name
    assert resp.description == view.description
    assert resp.system_prompt == view.system_prompt
    assert resp.provider == view.provider
    assert resp.model == view.model
    assert resp.allowed_tools == view.allowed_tools


def test_agent_config_response_none_provider_and_model():
    view = _agent_config_view(provider=None, model=None)
    resp = AgentConfigResponse(**view.__dict__)

    assert resp.provider is None
    assert resp.model is None


# ---------------------------------------------------------------------------
# AgentResponse
# ---------------------------------------------------------------------------


def test_agent_response_from_view():
    view = _agent_view()
    resp = AgentResponse.from_view(view)

    assert isinstance(resp, AgentResponse)
    assert isinstance(resp.config, AgentConfigResponse)
    assert resp.config.name == view.config.name
    assert resp.tools == view.tools
    assert resp.llm_info == view.llm_info


def test_agent_response_serialises_to_dict():
    resp = AgentResponse.from_view(_agent_view())
    data = resp.model_dump()

    assert data["config"]["name"] == "TestAgent"
    assert data["tools"] == ["echo"]
    assert "llm_info" in data


# ---------------------------------------------------------------------------
# WorkspaceResponse
# ---------------------------------------------------------------------------


def test_workspace_response_from_view():
    view = WorkspaceView(
        name="default",
        description="Default workspace",
        metadata={"env": "test"},
        agents=["Assistant"],
        tools=["echo"],
    )
    resp = WorkspaceResponse.from_view(view)

    assert resp.name == "default"
    assert resp.description == "Default workspace"
    assert resp.metadata == {"env": "test"}
    assert resp.agents == ["Assistant"]
    assert resp.tools == ["echo"]


def test_workspace_response_empty_defaults():
    view = WorkspaceView(name="empty", description="Empty")
    resp = WorkspaceResponse.from_view(view)

    assert resp.metadata == {}
    assert resp.agents == []
    assert resp.tools == []


# ---------------------------------------------------------------------------
# WorkspaceDetailResponse
# ---------------------------------------------------------------------------


def test_workspace_detail_response_from_view():
    agent_view = _agent_view()
    view = WorkspaceDetailView(
        name="default",
        description="Default workspace",
        agents=[agent_view],
        tools=["echo"],
    )
    resp = WorkspaceDetailResponse.from_view(view)

    assert resp.name == "default"
    assert len(resp.agents) == 1
    assert isinstance(resp.agents[0], AgentResponse)
    assert resp.agents[0].config.name == "TestAgent"


# ---------------------------------------------------------------------------
# ChatResponse
# ---------------------------------------------------------------------------


def test_chat_response():
    resp = ChatResponse(reply="Hello!")
    assert resp.reply == "Hello!"
    assert resp.model_dump() == {"reply": "Hello!"}


# ---------------------------------------------------------------------------
# ErrorResponse
# ---------------------------------------------------------------------------


def test_error_response_with_detail():
    resp = ErrorResponse(error="not_found", detail="workspace 'x' not found")
    assert resp.error == "not_found"
    assert resp.detail == "workspace 'x' not found"


def test_error_response_detail_defaults_to_none():
    resp = ErrorResponse(error="validation_error")
    assert resp.detail is None
