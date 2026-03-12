"""Unit tests for api.dependencies.

The dependency functions are plain callables — we test them directly without
starting a server or going through FastAPI's DI machinery.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from api.dependencies import get_agent_service, get_orchestrator, get_workspace_service
from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.services.agent_service import AgentService
from personal_assistant.services.workspace_service import WorkspaceService


def _make_request(orchestrator: Orchestrator) -> MagicMock:
    """Return a minimal mock Request with app.state.orchestrator set."""
    request = MagicMock()
    request.app.state.orchestrator = orchestrator
    return request


# ---------------------------------------------------------------------------
# get_orchestrator
# ---------------------------------------------------------------------------


def test_get_orchestrator_returns_instance_from_app_state(mock_registry):
    orchestrator = Orchestrator(mock_registry)
    request = _make_request(orchestrator)

    result = get_orchestrator(request)

    assert result is orchestrator


def test_get_orchestrator_identity_is_preserved(mock_registry):
    """Two requests sharing the same app.state return the same object."""
    orchestrator = Orchestrator(mock_registry)
    request_a = _make_request(orchestrator)
    request_b = _make_request(orchestrator)

    assert get_orchestrator(request_a) is get_orchestrator(request_b)


# ---------------------------------------------------------------------------
# get_workspace_service
# ---------------------------------------------------------------------------


def test_get_workspace_service_returns_workspace_service(mock_registry):
    orchestrator = Orchestrator(mock_registry)

    service = get_workspace_service(orchestrator)

    assert isinstance(service, WorkspaceService)


def test_get_workspace_service_wraps_given_orchestrator(mock_registry):
    orchestrator = Orchestrator(mock_registry)

    service = get_workspace_service(orchestrator)

    assert service._orchestrator is orchestrator


# ---------------------------------------------------------------------------
# get_agent_service
# ---------------------------------------------------------------------------


def test_get_agent_service_returns_agent_service(mock_registry):
    orchestrator = Orchestrator(mock_registry)

    service = get_agent_service(orchestrator)

    assert isinstance(service, AgentService)


def test_get_agent_service_wraps_given_orchestrator(mock_registry):
    orchestrator = Orchestrator(mock_registry)

    service = get_agent_service(orchestrator)

    assert service._orchestrator is orchestrator
