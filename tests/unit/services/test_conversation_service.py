"""Unit tests for ConversationService."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from personal_assistant.core.agent import Agent, AgentConfig
from personal_assistant.core.orchestrator import Orchestrator
from personal_assistant.services.conversation_pool import ConversationPool
from personal_assistant.services.conversation_service import ConversationService
from personal_assistant.services.exceptions import NotFoundError
from tests.unit.conftest import make_mock_graph, make_mock_provider


@contextmanager
def _patch_create_agent():
    """Patch create_agent so clone() doesn't invoke the real LangChain factory."""
    mock = make_mock_graph()
    with patch("personal_assistant.core.agent.create_agent", return_value=mock):
        yield mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def orchestrator():
    from personal_assistant.providers.registry import ProviderRegistry

    registry = ProviderRegistry()
    registry.register(make_mock_provider("mock"), default=True)
    return Orchestrator(registry)


@pytest.fixture
def workspace(orchestrator):
    from personal_assistant.core.workspace import WorkspaceConfig

    return orchestrator.create_workspace(WorkspaceConfig(name="ws", description="test ws"))


@pytest.fixture
def template(orchestrator, workspace):
    mock_graph = make_mock_graph()
    config = AgentConfig(name="Bot", description="test", system_prompt="Help.")
    with patch("personal_assistant.core.agent.create_agent", return_value=mock_graph):
        return orchestrator.create_agent(config, "ws")


@pytest.fixture
def pool():
    return ConversationPool()


@pytest.fixture
def service(orchestrator, pool):
    return ConversationService(orchestrator, pool)


# ---------------------------------------------------------------------------
# Pool hit
# ---------------------------------------------------------------------------


class TestGetOrCreateClonePoolHit:
    async def test_returns_existing_clone(self, service, pool, workspace, template):
        cid = uuid.uuid4()
        with _patch_create_agent():
            existing_clone = template.clone()
        pool.put("ws", "Bot", cid, existing_clone)

        clone, returned_id = await service.get_or_create_clone("ws", "Bot", cid, session=None)
        assert clone is existing_clone
        assert returned_id == cid


# ---------------------------------------------------------------------------
# New conversation (id=None)
# ---------------------------------------------------------------------------


class TestGetOrCreateCloneNewConversation:
    async def test_returns_clone_with_new_uuid_no_session(self, service, workspace, template):
        with _patch_create_agent():
            clone, conv_id = await service.get_or_create_clone("ws", "Bot", None, session=None)
        assert clone is not template
        assert isinstance(conv_id, uuid.UUID)
        assert clone._conversation_id == conv_id
        assert clone._history_loaded is True

    async def test_clone_added_to_pool(self, service, pool, workspace, template):
        with _patch_create_agent():
            clone, conv_id = await service.get_or_create_clone("ws", "Bot", None, session=None)
        assert pool.get("ws", "Bot", conv_id) is clone

    async def test_template_not_mutated(self, service, workspace, template):
        with _patch_create_agent():
            await service.get_or_create_clone("ws", "Bot", None, session=None)
        assert template.history == []
        assert template.conversation_id is None

    async def test_with_session_calls_start_conversation(self, service, workspace, template):
        mock_session = MagicMock()
        new_uuid = uuid.uuid4()

        async def fake_start(self_agent, session, ws_name, user_id=None):
            self_agent._conversation_id = new_uuid
            self_agent._history_loaded = True
            self_agent._history = []
            return new_uuid

        with _patch_create_agent():
            with patch.object(Agent, "start_conversation", new=fake_start):
                _, conv_id = await service.get_or_create_clone("ws", "Bot", None, mock_session)
        assert conv_id == new_uuid


# ---------------------------------------------------------------------------
# Cold-start (id given, not in pool)
# ---------------------------------------------------------------------------


class TestGetOrCreateCloneColdStart:
    async def test_no_session_raises_not_found(self, service, workspace, template):
        cid = uuid.uuid4()
        with pytest.raises(NotFoundError):
            await service.get_or_create_clone("ws", "Bot", cid, session=None)

    async def test_unknown_conversation_in_db_raises_not_found(self, service, workspace, template):
        cid = uuid.uuid4()
        mock_session = MagicMock()

        with patch("personal_assistant.persistence.repository.ConversationRepository") as MockRepo:
            repo_instance = AsyncMock()
            repo_instance.get_conversation_for_agent = AsyncMock(return_value=None)
            MockRepo.return_value = repo_instance

            with pytest.raises(NotFoundError):
                await service.get_or_create_clone("ws", "Bot", cid, session=mock_session)

    async def test_valid_conversation_returns_clone_with_lazy_load(
        self, service, pool, workspace, template
    ):
        cid = uuid.uuid4()
        mock_session = MagicMock()
        fake_conv = MagicMock()
        fake_conv.id = cid

        with _patch_create_agent():
            with patch(
                "personal_assistant.persistence.repository.ConversationRepository"
            ) as MockRepo:
                repo_instance = AsyncMock()
                repo_instance.get_conversation_for_agent = AsyncMock(return_value=fake_conv)
                MockRepo.return_value = repo_instance

                clone, returned_id = await service.get_or_create_clone(
                    "ws", "Bot", cid, session=mock_session
                )

        assert returned_id == cid
        assert clone is not template
        assert clone.conversation_id == cid
        assert clone._history_loaded is False
        assert pool.get("ws", "Bot", cid) is clone


# ---------------------------------------------------------------------------
# Unknown workspace / agent
# ---------------------------------------------------------------------------


class TestGetOrCreateCloneNotFound:
    async def test_unknown_workspace_raises(self, service):
        with pytest.raises(NotFoundError):
            await service.get_or_create_clone("ghost", "Bot", None, session=None)

    async def test_unknown_agent_raises(self, service, workspace):
        with pytest.raises(NotFoundError):
            await service.get_or_create_clone("ws", "ghost", None, session=None)


# ---------------------------------------------------------------------------
# llm_override
# ---------------------------------------------------------------------------


class TestGetOrCreateCloneLlmOverride:
    async def test_override_clone_uses_given_llm(self, service, workspace, template):
        from unittest.mock import MagicMock

        from langchain_core.language_models import BaseChatModel

        override_llm = MagicMock(spec=BaseChatModel)
        with _patch_create_agent():
            clone, _ = await service.get_or_create_clone(
                "ws", "Bot", None, session=None, llm_override=override_llm
            )
        assert clone._llm is override_llm

    async def test_override_clone_not_added_to_pool(self, service, pool, workspace, template):
        from unittest.mock import MagicMock

        from langchain_core.language_models import BaseChatModel

        override_llm = MagicMock(spec=BaseChatModel)
        with _patch_create_agent():
            _, conv_id = await service.get_or_create_clone(
                "ws", "Bot", None, session=None, llm_override=override_llm
            )
        assert pool.get("ws", "Bot", conv_id) is None

    async def test_override_template_not_mutated(self, service, workspace, template):
        from unittest.mock import MagicMock

        from langchain_core.language_models import BaseChatModel

        original_llm = template._llm
        override_llm = MagicMock(spec=BaseChatModel)
        with _patch_create_agent():
            await service.get_or_create_clone(
                "ws", "Bot", None, session=None, llm_override=override_llm
            )
        assert template._llm is original_llm

    async def test_override_uses_provided_conversation_id(self, service, workspace, template):
        import uuid
        from unittest.mock import MagicMock

        from langchain_core.language_models import BaseChatModel

        override_llm = MagicMock(spec=BaseChatModel)
        cid = uuid.uuid4()
        with _patch_create_agent():
            _, returned_id = await service.get_or_create_clone(
                "ws", "Bot", cid, session=None, llm_override=override_llm
            )
        assert returned_id == cid


# ---------------------------------------------------------------------------
# reset_conversation
# ---------------------------------------------------------------------------


class TestResetConversation:
    async def test_evicts_clone(self, service, pool, workspace, template):
        with _patch_create_agent():
            _, cid = await service.get_or_create_clone("ws", "Bot", None, session=None)
        assert pool.get("ws", "Bot", cid) is not None

        service.reset_conversation("ws", "Bot", cid)
        assert pool.get("ws", "Bot", cid) is None
