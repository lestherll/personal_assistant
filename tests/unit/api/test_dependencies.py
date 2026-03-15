"""Unit tests for api.dependencies."""

from __future__ import annotations

from unittest.mock import MagicMock

from api.dependencies import (
    DEV_USER,
    get_agent_service,
    get_workspace_service,
)
from personal_assistant.services.agent_service import AgentService
from personal_assistant.services.workspace_service import WorkspaceService


def _make_request(agent_service=None, workspace_service=None) -> MagicMock:
    request = MagicMock()
    request.app.state.agent_service = agent_service or MagicMock(spec=AgentService)
    request.app.state.workspace_service = workspace_service or MagicMock(spec=WorkspaceService)
    return request


# ---------------------------------------------------------------------------
# get_workspace_service
# ---------------------------------------------------------------------------


def test_get_workspace_service_returns_singleton_from_app_state():
    svc = MagicMock(spec=WorkspaceService)
    request = _make_request(workspace_service=svc)
    result = get_workspace_service(request)
    assert result is svc


def test_get_workspace_service_identity_is_preserved():
    svc = MagicMock(spec=WorkspaceService)
    request_a = _make_request(workspace_service=svc)
    request_b = _make_request(workspace_service=svc)
    assert get_workspace_service(request_a) is get_workspace_service(request_b)


# ---------------------------------------------------------------------------
# get_agent_service
# ---------------------------------------------------------------------------


def test_get_agent_service_returns_singleton_from_app_state():
    svc = MagicMock(spec=AgentService)
    request = _make_request(agent_service=svc)
    result = get_agent_service(request)
    assert result is svc


def test_get_agent_service_identity_is_preserved():
    svc = MagicMock(spec=AgentService)
    request_a = _make_request(agent_service=svc)
    request_b = _make_request(agent_service=svc)
    assert get_agent_service(request_a) is get_agent_service(request_b)


# ---------------------------------------------------------------------------
# DEV_USER sentinel
# ---------------------------------------------------------------------------


def test_dev_user_has_zero_uuid():
    import uuid

    assert DEV_USER.id == uuid.UUID(int=0)
