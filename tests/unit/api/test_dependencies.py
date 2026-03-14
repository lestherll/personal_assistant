"""Unit tests for api.dependencies.

The dependency functions are plain callables — we test them directly without
starting a server or going through FastAPI's DI machinery.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from api.dependencies import (
    get_agent_service,
    get_conversation_pool,
    get_conversation_service,
    get_orchestrator,
    get_workspace_service,
)
from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.services.agent_service import AgentService
from personal_assistant.services.conversation_pool import ConversationPool
from personal_assistant.services.conversation_service import ConversationService
from personal_assistant.services.workspace_service import WorkspaceService


def _make_request(orchestrator: Orchestrator, pool: ConversationPool | None = None) -> MagicMock:
    """Return a minimal mock Request with required app.state attributes set."""
    request = MagicMock()
    request.app.state.orchestrator = orchestrator
    request.app.state.conversation_pool = pool or ConversationPool()
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
# get_conversation_pool
# ---------------------------------------------------------------------------


def test_get_conversation_pool_returns_pool_from_app_state(mock_registry):
    orchestrator = Orchestrator(mock_registry)
    pool = ConversationPool(max_size=50)
    request = _make_request(orchestrator, pool)

    result = get_conversation_pool(request)

    assert result is pool


# ---------------------------------------------------------------------------
# get_workspace_service
# ---------------------------------------------------------------------------


def test_get_workspace_service_returns_workspace_service(mock_registry):
    orchestrator = Orchestrator(mock_registry)
    pool = ConversationPool()
    conv_service = ConversationService(orchestrator, pool)

    service = get_workspace_service(orchestrator, conv_service)

    assert isinstance(service, WorkspaceService)


def test_get_workspace_service_wraps_given_orchestrator(mock_registry):
    orchestrator = Orchestrator(mock_registry)
    pool = ConversationPool()
    conv_service = ConversationService(orchestrator, pool)

    service = get_workspace_service(orchestrator, conv_service)

    assert service._orchestrator is orchestrator


# ---------------------------------------------------------------------------
# get_conversation_service
# ---------------------------------------------------------------------------


def test_get_conversation_service_returns_conversation_service(mock_registry):
    orchestrator = Orchestrator(mock_registry)
    pool = ConversationPool()

    service = get_conversation_service(orchestrator, pool)

    assert isinstance(service, ConversationService)


def test_get_conversation_service_uses_given_pool(mock_registry):
    orchestrator = Orchestrator(mock_registry)
    pool = ConversationPool()

    service = get_conversation_service(orchestrator, pool)

    assert service._pool is pool


# ---------------------------------------------------------------------------
# get_agent_service
# ---------------------------------------------------------------------------


def test_get_agent_service_returns_agent_service(mock_registry):
    orchestrator = Orchestrator(mock_registry)
    pool = ConversationPool()
    conv_service = ConversationService(orchestrator, pool)

    service = get_agent_service(orchestrator, conv_service)

    assert isinstance(service, AgentService)


def test_get_agent_service_wraps_given_orchestrator(mock_registry):
    orchestrator = Orchestrator(mock_registry)
    pool = ConversationPool()
    conv_service = ConversationService(orchestrator, pool)

    service = get_agent_service(orchestrator, conv_service)

    assert service._orchestrator is orchestrator
