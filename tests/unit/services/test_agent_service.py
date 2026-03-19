"""Tests for the new DB-first, stateless AgentService."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from personal_assistant.services.conversation_cache import InMemoryConversationCache
from personal_assistant.services.exceptions import AlreadyExistsError, NotFoundError
from personal_assistant.services.views import AgentView, ConversationView
from tests.unit.conftest import make_mock_graph, make_mock_provider

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_id():
    return uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def registry():
    from personal_assistant.providers.registry import ProviderRegistry

    reg = ProviderRegistry()
    reg.register(make_mock_provider("mock"), default=True)
    return reg


@pytest.fixture
def cache():
    return InMemoryConversationCache(max_size=32)


@pytest.fixture
def service(registry, cache):
    from personal_assistant.services.agent_service import AgentService

    return AgentService(registry, tools=[], cache=cache)


@pytest.fixture
def mock_ws_row(user_id):
    """Fake UserWorkspace ORM row."""
    row = MagicMock()
    row.id = uuid.uuid4()
    row.user_id = user_id
    row.name = "ws"
    row.description = "test ws"
    return row


@pytest.fixture
def mock_agent_row(mock_ws_row):
    """Fake UserAgent ORM row."""
    row = MagicMock()
    row.id = uuid.uuid4()
    row.user_workspace_id = mock_ws_row.id
    row.name = "Bot"
    row.description = "A bot"
    row.system_prompt = "Be helpful."
    row.provider = None
    row.model = None
    row.allowed_tools = None
    return row


def _mock_ws_repo(ws_row=None, agent_row=None, agent_rows=None):
    """Build a mocked UserWorkspaceRepository."""
    repo = MagicMock()
    repo.get_workspace = AsyncMock(return_value=ws_row)
    repo.list_workspaces = AsyncMock(return_value=[ws_row] if ws_row else [])
    repo.create_workspace = AsyncMock(return_value=ws_row)
    repo.upsert_workspace = AsyncMock(return_value=ws_row)
    repo.delete_workspace = AsyncMock(return_value=True)
    repo.get_agent = AsyncMock(return_value=agent_row)
    repo.list_agents = AsyncMock(return_value=agent_rows or ([agent_row] if agent_row else []))
    repo.create_agent = AsyncMock(return_value=agent_row)
    repo.upsert_agent = AsyncMock(return_value=agent_row)
    repo.delete_agent = AsyncMock(return_value=True)
    return repo


def _mock_conv_repo(conv=None, messages=None, deleted=True):
    """Build a mocked ConversationRepository."""
    repo = AsyncMock()
    repo.get_conversation = AsyncMock(return_value=conv)
    repo.get_conversation_for_workspace = AsyncMock(return_value=conv)
    repo.create_conversation = AsyncMock(return_value=conv)
    repo.load_messages = AsyncMock(return_value=messages or [])
    repo.add_message = AsyncMock()
    repo.touch_conversation = AsyncMock()
    repo.update_title = AsyncMock()
    repo.delete_conversation = AsyncMock(return_value=deleted)
    repo.list_conversations = AsyncMock(return_value=[conv] if conv else [])
    repo.list_agent_participation = AsyncMock(return_value=[])
    return repo


def _make_mock_conv(conv_id=None, workspace_id=None, user_id=None):
    conv = MagicMock()
    conv.id = conv_id or uuid.uuid4()
    conv.workspace_id = workspace_id or uuid.uuid4()
    conv.user_id = user_id
    conv.created_at = datetime.now(UTC)
    conv.updated_at = datetime.now(UTC)
    return conv


def _make_mock_graph(response: str = "Test response") -> MagicMock:
    return make_mock_graph(response)


def _patch_ws_repo(ws_repo):
    return patch(
        "personal_assistant.services.agent_service.UserWorkspaceRepository",
        return_value=ws_repo,
    )


def _patch_conv_repo(conv_repo):
    """Patch ConversationRepository in both agent_service (module-level import) and
    the source persistence module (used by agent.py's lazy imports)."""
    from contextlib import ExitStack

    class _MultiPatch:
        def __enter__(self):
            self._stack = ExitStack()
            # Covers agent_service.py top-level import
            self._stack.enter_context(
                patch(
                    "personal_assistant.services.agent_service.ConversationRepository",
                    return_value=conv_repo,
                )
            )
            # Covers agent.py lazy imports for ConversationRepository
            self._stack.enter_context(
                patch(
                    "personal_assistant.persistence.repository.ConversationRepository",
                    return_value=conv_repo,
                )
            )
            return self

        def __exit__(self, *args):
            self._stack.__exit__(*args)

    return _MultiPatch()


def _patch_graph():
    mock = _make_mock_graph()
    return patch("personal_assistant.core.agent.create_agent", return_value=mock), mock


# ---------------------------------------------------------------------------
# CRUD: create_agent
# ---------------------------------------------------------------------------


class TestCreateAgent:
    async def test_creates_and_returns_view(self, service, user_id, mock_ws_row, mock_agent_row):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=None)
        ws_repo.create_agent = AsyncMock(return_value=mock_agent_row)

        with _patch_ws_repo(ws_repo):
            view = await service.create_agent(
                user_id,
                "ws",
                name="Bot",
                description="A bot",
                system_prompt="Be helpful.",
                session=session,
            )

        assert isinstance(view, AgentView)
        assert view.config.name == "Bot"
        assert view.config.system_prompt == "Be helpful."

    async def test_duplicate_agent_raises(self, service, user_id, mock_ws_row, mock_agent_row):
        session = MagicMock()
        # get_agent returns existing row → should raise AlreadyExistsError
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=mock_agent_row)

        with _patch_ws_repo(ws_repo), pytest.raises(AlreadyExistsError):
            await service.create_agent(
                user_id, "ws", name="Bot", description="x", system_prompt="y", session=session
            )

    async def test_unknown_workspace_raises(self, service, user_id):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_row=None)

        with _patch_ws_repo(ws_repo), pytest.raises(NotFoundError):
            await service.create_agent(
                user_id, "ghost", name="Bot", description="x", system_prompt="y", session=session
            )


# ---------------------------------------------------------------------------
# CRUD: list_agents
# ---------------------------------------------------------------------------


class TestListAgents:
    async def test_returns_all_agents(self, service, user_id, mock_ws_row, mock_agent_row):
        session = MagicMock()
        second_row = MagicMock()
        second_row.name = "Alpha"
        second_row.description = "x"
        second_row.system_prompt = "y"
        second_row.provider = None
        second_row.model = None
        second_row.allowed_tools = None

        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_rows=[mock_agent_row, second_row])

        with _patch_ws_repo(ws_repo):
            views = await service.list_agents(user_id, "ws", session=session)

        assert len(views) == 2

    async def test_unknown_workspace_raises(self, service, user_id):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_row=None)

        with _patch_ws_repo(ws_repo), pytest.raises(NotFoundError):
            await service.list_agents(user_id, "ghost", session=session)

    async def test_passes_pagination_to_repository(
        self, service, user_id, mock_ws_row, mock_agent_row
    ):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_rows=[mock_agent_row])

        with _patch_ws_repo(ws_repo):
            await service.list_agents(user_id, "ws", skip=4, limit=11, session=session)

        ws_repo.list_agents.assert_awaited_once_with(mock_ws_row.id, skip=4, limit=11)


# ---------------------------------------------------------------------------
# CRUD: get_agent
# ---------------------------------------------------------------------------


class TestGetAgent:
    async def test_returns_view(self, service, user_id, mock_ws_row, mock_agent_row):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=mock_agent_row)

        with _patch_ws_repo(ws_repo):
            view = await service.get_agent(user_id, "ws", "Bot", session=session)

        assert view.config.name == "Bot"

    async def test_unknown_workspace_raises(self, service, user_id):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_row=None)

        with _patch_ws_repo(ws_repo), pytest.raises(NotFoundError):
            await service.get_agent(user_id, "ghost", "Bot", session=session)

    async def test_unknown_agent_raises(self, service, user_id, mock_ws_row):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=None)

        with _patch_ws_repo(ws_repo), pytest.raises(NotFoundError):
            await service.get_agent(user_id, "ws", "ghost", session=session)


# ---------------------------------------------------------------------------
# _row_to_view: tool resolution
# ---------------------------------------------------------------------------


class TestRowToViewToolResolution:
    """Verify that _row_to_view resolves tools correctly."""

    def _make_tool(self, name: str):
        from unittest.mock import MagicMock

        t = MagicMock()
        t.name = name
        return t

    def _make_row(self, allowed_tools: list[str]):
        row = MagicMock()
        row.name = "Bot"
        row.description = "desc"
        row.system_prompt = "prompt"
        row.provider = None
        row.model = None
        row.allowed_tools = allowed_tools
        return row

    def _make_service(self, tool_names: list[str]):
        from personal_assistant.providers.registry import ProviderRegistry
        from personal_assistant.services.agent_service import AgentService
        from personal_assistant.services.conversation_cache import InMemoryConversationCache
        from tests.unit.conftest import make_mock_provider

        reg = ProviderRegistry()
        reg.register(make_mock_provider("mock"), default=True)
        tools = [self._make_tool(n) for n in tool_names]
        cache = InMemoryConversationCache(max_size=8)
        return AgentService(reg, tools=tools, cache=cache)

    def test_none_allowed_tools_returns_all_global_tools(self):
        svc = self._make_service(["echo", "search"])
        row = self._make_row(allowed_tools=None)
        view = svc._row_to_view(row)
        assert view.tools == ["echo", "search"]
        assert view.config.allowed_tools is None

    def test_empty_allowed_tools_returns_no_tools(self):
        svc = self._make_service(["echo", "search"])
        row = self._make_row(allowed_tools=[])
        view = svc._row_to_view(row)
        assert view.tools == []
        assert view.config.allowed_tools == []

    def test_explicit_allowed_tools_filters_global_tools(self):
        svc = self._make_service(["echo", "search", "indeed"])
        row = self._make_row(allowed_tools=["echo", "indeed"])
        view = svc._row_to_view(row)
        assert view.tools == ["echo", "indeed"]
        assert view.config.allowed_tools == ["echo", "indeed"]

    def test_nonexistent_allowed_tool_returns_empty(self):
        svc = self._make_service(["echo"])
        row = self._make_row(allowed_tools=["nonexistent"])
        view = svc._row_to_view(row)
        assert view.tools == []

    def test_no_global_tools_returns_empty(self):
        svc = self._make_service([])
        row = self._make_row(allowed_tools=None)
        view = svc._row_to_view(row)
        assert view.tools == []


# ---------------------------------------------------------------------------
# CRUD: update_agent
# ---------------------------------------------------------------------------


class TestUpdateAgent:
    async def test_updates_fields(self, service, user_id, mock_ws_row, mock_agent_row):
        session = MagicMock()
        updated_row = MagicMock()
        updated_row.name = "Bot"
        updated_row.description = "A bot"
        updated_row.system_prompt = "New prompt."
        updated_row.provider = None
        updated_row.model = None
        updated_row.allowed_tools = None

        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=mock_agent_row)
        ws_repo.upsert_agent = AsyncMock(return_value=updated_row)

        with _patch_ws_repo(ws_repo):
            view = await service.update_agent(
                user_id, "ws", "Bot", system_prompt="New prompt.", session=session
            )

        assert view.config.system_prompt == "New prompt."

    async def test_unknown_workspace_raises(self, service, user_id):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_row=None)

        with _patch_ws_repo(ws_repo), pytest.raises(NotFoundError):
            await service.update_agent(user_id, "ghost", "Bot", session=session)

    async def test_unknown_agent_raises(self, service, user_id, mock_ws_row):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=None)

        with _patch_ws_repo(ws_repo), pytest.raises(NotFoundError):
            await service.update_agent(user_id, "ws", "ghost", session=session)


# ---------------------------------------------------------------------------
# CRUD: delete_agent
# ---------------------------------------------------------------------------


class TestDeleteAgent:
    async def test_deletes_agent(self, service, user_id, mock_ws_row, mock_agent_row):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=mock_agent_row)

        with _patch_ws_repo(ws_repo):
            await service.delete_agent(user_id, "ws", "Bot", session=session)

        ws_repo.delete_agent.assert_called_once_with(mock_ws_row.id, "Bot")

    async def test_unknown_workspace_raises(self, service, user_id):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_row=None)

        with _patch_ws_repo(ws_repo), pytest.raises(NotFoundError):
            await service.delete_agent(user_id, "ghost", "Bot", session=session)

    async def test_unknown_agent_raises(self, service, user_id, mock_ws_row):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=None)

        with _patch_ws_repo(ws_repo), pytest.raises(NotFoundError):
            await service.delete_agent(user_id, "ws", "ghost", session=session)


# ---------------------------------------------------------------------------
# run_agent
# ---------------------------------------------------------------------------


class TestRunAgent:
    async def test_returns_reply_and_new_conv_id(
        self, service, user_id, mock_ws_row, mock_agent_row
    ):
        session = AsyncMock()
        conv = _make_mock_conv(workspace_id=mock_ws_row.id, user_id=user_id)
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=mock_agent_row)
        conv_repo = _mock_conv_repo(conv=conv)

        patcher, _ = _patch_graph()
        with patcher, _patch_ws_repo(ws_repo), _patch_conv_repo(conv_repo):
            reply, conv_id = await service.run_agent(
                user_id, "ws", "Bot", "Hello", conversation_id=None, session=session
            )

        assert reply == "Test response"
        assert isinstance(conv_id, uuid.UUID)

    async def test_reuses_existing_conversation(
        self, service, user_id, mock_ws_row, mock_agent_row, cache
    ):
        session = AsyncMock()
        existing_conv_id = uuid.uuid4()
        conv = _make_mock_conv(
            conv_id=existing_conv_id, workspace_id=mock_ws_row.id, user_id=user_id
        )
        messages = [HumanMessage(content="prev"), AIMessage(content="ok")]

        # Pre-populate cache using workspace UUID (not string)
        await cache.set(user_id, mock_ws_row.id, existing_conv_id, messages)

        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=mock_agent_row)
        conv_repo = _mock_conv_repo(conv=conv)

        patcher, _ = _patch_graph()
        with patcher, _patch_ws_repo(ws_repo), _patch_conv_repo(conv_repo):
            _reply, conv_id = await service.run_agent(
                user_id, "ws", "Bot", "Hello", conversation_id=existing_conv_id, session=session
            )

        assert conv_id == existing_conv_id
        # Cache was a hit, so load_messages should NOT be called
        conv_repo.load_messages.assert_not_called()

    async def test_loads_history_from_db_on_cache_miss(
        self, service, user_id, mock_ws_row, mock_agent_row
    ):
        session = AsyncMock()
        existing_conv_id = uuid.uuid4()
        conv = _make_mock_conv(
            conv_id=existing_conv_id, workspace_id=mock_ws_row.id, user_id=user_id
        )
        # No cache pre-population → should hit DB
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=mock_agent_row)
        conv_repo = _mock_conv_repo(conv=conv)

        patcher, _ = _patch_graph()
        with patcher, _patch_ws_repo(ws_repo), _patch_conv_repo(conv_repo):
            await service.run_agent(
                user_id, "ws", "Bot", "Hello", conversation_id=existing_conv_id, session=session
            )

        conv_repo.load_messages.assert_called_once_with(existing_conv_id)

    async def test_unknown_workspace_raises(self, service, user_id):
        session = AsyncMock()
        ws_repo = _mock_ws_repo(ws_row=None)

        with _patch_ws_repo(ws_repo), pytest.raises(NotFoundError):
            await service.run_agent(
                user_id, "ghost", "Bot", "Hi", conversation_id=None, session=session
            )

    async def test_unknown_agent_raises(self, service, user_id, mock_ws_row):
        session = AsyncMock()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=None)

        with _patch_ws_repo(ws_repo), pytest.raises(NotFoundError):
            await service.run_agent(
                user_id, "ws", "ghost", "Hi", conversation_id=None, session=session
            )

    async def test_invalid_conversation_id_raises(
        self, service, user_id, mock_ws_row, mock_agent_row
    ):
        """If conv_id is given but doesn't belong to this user/workspace/agent → NotFoundError."""
        session = AsyncMock()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=mock_agent_row)
        # get_conversation_for_workspace returns None → not found
        conv_repo = _mock_conv_repo(conv=None)

        with _patch_ws_repo(ws_repo), _patch_conv_repo(conv_repo), pytest.raises(NotFoundError):
            await service.run_agent(
                user_id, "ws", "Bot", "Hi", conversation_id=uuid.uuid4(), session=session
            )

    async def test_cache_is_updated_after_run(
        self, service, user_id, mock_ws_row, mock_agent_row, cache
    ):
        session = AsyncMock()
        conv = _make_mock_conv(workspace_id=mock_ws_row.id, user_id=user_id)
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=mock_agent_row)
        conv_repo = _mock_conv_repo(conv=conv)

        patcher, _ = _patch_graph()
        with patcher, _patch_ws_repo(ws_repo), _patch_conv_repo(conv_repo):
            _, conv_id = await service.run_agent(
                user_id, "ws", "Bot", "Hello", conversation_id=None, session=session
            )

        # Cache should now contain the conversation (keyed by workspace UUID)
        cached = await cache.get(user_id, mock_ws_row.id, conv_id)
        assert cached is not None


# ---------------------------------------------------------------------------
# Conversation title
# ---------------------------------------------------------------------------


class TestConversationTitle:
    async def test_run_agent_generates_title_on_first_turn_with_resolved_conv_id(
        self, service, user_id
    ):
        session = AsyncMock()
        conv_id = uuid.uuid4()
        ws_row = MagicMock()
        ws_row.id = uuid.uuid4()

        agent = MagicMock()
        agent.history = []
        agent.llm = MagicMock()
        agent.conversation_id = conv_id
        agent.run = AsyncMock(return_value=MagicMock(content="ok"))

        service._prepare_agent = AsyncMock(return_value=(agent, ws_row))
        service._cache.set = AsyncMock()
        service.rename_conversation = AsyncMock()

        with patch(
            "personal_assistant.services.agent_service._generate_title",
            new=AsyncMock(return_value="My Title"),
        ) as mock_generate_title:
            await service.run_agent(
                user_id,
                "ws",
                "Bot",
                "Hello there",
                conversation_id=None,
                session=session,
            )

        mock_generate_title.assert_awaited_once_with("Hello there", agent.llm)
        service.rename_conversation.assert_awaited_once_with(
            user_id=user_id,
            workspace_name="ws",
            conversation_id=conv_id,
            title="My Title",
            session=session,
        )

    async def test_run_agent_skips_title_generation_on_subsequent_turn(self, service, user_id):
        session = AsyncMock()
        conv_id = uuid.uuid4()
        ws_row = MagicMock()
        ws_row.id = uuid.uuid4()

        agent = MagicMock()
        agent.history = [HumanMessage(content="First message")]
        agent.llm = MagicMock()
        agent.conversation_id = conv_id
        agent.run = AsyncMock(return_value=MagicMock(content="ok"))

        service._prepare_agent = AsyncMock(return_value=(agent, ws_row))
        service._cache.set = AsyncMock()
        service.rename_conversation = AsyncMock()

        with patch(
            "personal_assistant.services.agent_service._generate_title",
            new=AsyncMock(return_value="Should Not Be Used"),
        ) as mock_generate_title:
            await service.run_agent(
                user_id,
                "ws",
                "Bot",
                "Second message",
                conversation_id=conv_id,
                session=session,
            )

        mock_generate_title.assert_not_awaited()
        service.rename_conversation.assert_not_awaited()

    async def test_stream_agent_generates_title_before_tokens(self, service, user_id):
        session = AsyncMock()
        conv_id = uuid.uuid4()
        ws_row = MagicMock()
        ws_row.id = uuid.uuid4()

        async def _stream(*args, **kwargs):
            yield MagicMock(content="hello")

        agent = MagicMock()
        agent.history = []
        agent.llm = MagicMock()
        agent.conversation_id = conv_id
        agent.stream = _stream

        service._prepare_agent = AsyncMock(return_value=(agent, ws_row))
        service._cache.set = AsyncMock()
        service.rename_conversation = AsyncMock()

        with patch(
            "personal_assistant.services.agent_service._generate_title",
            new=AsyncMock(return_value="Stream Title"),
        ) as mock_generate_title:
            tokens, returned_conv_id = await service.stream_agent(
                user_id,
                "ws",
                "Bot",
                "Start stream",
                conversation_id=None,
                session=session,
            )

        assert returned_conv_id == conv_id
        mock_generate_title.assert_awaited_once_with("Start stream", agent.llm)
        service.rename_conversation.assert_awaited_once_with(
            user_id=user_id,
            workspace_name="ws",
            conversation_id=conv_id,
            title="Stream Title",
            session=session,
        )

        chunks = [chunk async for chunk in tokens]
        assert chunks == ["hello"]


# ---------------------------------------------------------------------------
# stream_agent
# ---------------------------------------------------------------------------


class TestStreamAgent:
    async def test_returns_iterator_and_conv_id(
        self, service, user_id, mock_ws_row, mock_agent_row
    ):
        session = AsyncMock()
        conv = _make_mock_conv(workspace_id=mock_ws_row.id, user_id=user_id)
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=mock_agent_row)
        conv_repo = _mock_conv_repo(conv=conv)

        patcher, _ = _patch_graph()
        with patcher, _patch_ws_repo(ws_repo), _patch_conv_repo(conv_repo):
            tokens, conv_id = await service.stream_agent(
                user_id, "ws", "Bot", "Hello", conversation_id=None, session=session
            )
            assert isinstance(conv_id, uuid.UUID)
            chunks = [c async for c in tokens]

        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)

    async def test_unknown_workspace_raises(self, service, user_id):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_row=None)

        with _patch_ws_repo(ws_repo), pytest.raises(NotFoundError):
            await service.stream_agent(
                user_id, "ghost", "Bot", "Hi", conversation_id=None, session=session
            )

    async def test_unknown_agent_raises(self, service, user_id, mock_ws_row):
        session = MagicMock()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=None)

        with _patch_ws_repo(ws_repo), pytest.raises(NotFoundError):
            await service.stream_agent(
                user_id, "ws", "ghost", "Hi", conversation_id=None, session=session
            )


# ---------------------------------------------------------------------------
# list_conversations
# ---------------------------------------------------------------------------


class TestListConversations:
    async def test_returns_views(self, service, user_id, mock_ws_row):
        session = MagicMock()
        conv_id = uuid.uuid4()
        conv = _make_mock_conv(conv_id=conv_id, workspace_id=mock_ws_row.id, user_id=user_id)
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row)
        conv_repo = _mock_conv_repo(conv=conv)

        with _patch_ws_repo(ws_repo), _patch_conv_repo(conv_repo):
            views = await service.list_conversations(user_id, "ws", session=session)

        assert len(views) == 1
        assert isinstance(views[0], ConversationView)
        assert views[0].id == conv_id
        assert views[0].workspace_id == mock_ws_row.id

    async def test_none_user_id_raises(self, service):
        session = MagicMock()
        with pytest.raises(NotFoundError):
            await service.list_conversations(None, "ws", session=session)

    async def test_passes_pagination_to_repository(self, service, user_id, mock_ws_row):
        session = MagicMock()
        conv = _make_mock_conv(workspace_id=mock_ws_row.id, user_id=user_id)
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row)
        conv_repo = _mock_conv_repo(conv=conv)

        with _patch_ws_repo(ws_repo), _patch_conv_repo(conv_repo):
            await service.list_conversations(user_id, "ws", session=session, skip=6, limit=15)

        conv_repo.list_conversations.assert_awaited_once_with(
            mock_ws_row.id,
            user_id=user_id,
            skip=6,
            limit=15,
            search_term=None,
        )


# ---------------------------------------------------------------------------
# delete_conversation
# ---------------------------------------------------------------------------


class TestDeleteConversation:
    async def test_deletes_and_invalidates_cache(self, service, user_id, mock_ws_row, cache):
        session = AsyncMock()
        conv_id = uuid.uuid4()
        conv = _make_mock_conv(conv_id=conv_id, workspace_id=mock_ws_row.id, user_id=user_id)
        # Pre-populate cache using workspace UUID
        await cache.set(user_id, mock_ws_row.id, conv_id, [HumanMessage(content="hi")])

        ws_repo = _mock_ws_repo(ws_row=mock_ws_row)
        conv_repo = _mock_conv_repo(conv=conv)

        with _patch_ws_repo(ws_repo), _patch_conv_repo(conv_repo):
            await service.delete_conversation(user_id, "ws", conv_id, session=session)

        # Cache entry should be gone
        assert await cache.get(user_id, mock_ws_row.id, conv_id) is None

    async def test_not_found_raises(self, service, user_id, mock_ws_row):
        session = AsyncMock()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row)
        conv_repo = _mock_conv_repo(conv=None)

        with _patch_ws_repo(ws_repo), _patch_conv_repo(conv_repo), pytest.raises(NotFoundError):
            await service.delete_conversation(user_id, "ws", uuid.uuid4(), session=session)


# ---------------------------------------------------------------------------
# get_conversation_messages
# ---------------------------------------------------------------------------


class TestGetConversationMessages:
    async def test_returns_messages(self, service, user_id, mock_ws_row):
        session = AsyncMock()
        conv_id = uuid.uuid4()
        conv = _make_mock_conv(conv_id=conv_id, workspace_id=mock_ws_row.id, user_id=user_id)

        msg = MagicMock()
        msg.id = uuid.uuid4()
        msg.conversation_id = conv_id
        msg.role = "human"
        msg.content = "hello"
        msg.agent_id = None
        msg.created_at = datetime.now(UTC)

        ws_repo = _mock_ws_repo(ws_row=mock_ws_row)
        conv_repo = _mock_conv_repo(conv=conv, messages=[msg])

        with _patch_ws_repo(ws_repo), _patch_conv_repo(conv_repo):
            views = await service.get_conversation_messages(user_id, "ws", conv_id, session=session)

        assert len(views) == 1
        assert views[0].content == "hello"
        assert views[0].role == "human"

    async def test_not_found_raises(self, service, user_id, mock_ws_row):
        session = AsyncMock()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row)
        conv_repo = _mock_conv_repo(conv=None)

        with _patch_ws_repo(ws_repo), _patch_conv_repo(conv_repo), pytest.raises(NotFoundError):
            await service.get_conversation_messages(user_id, "ws", uuid.uuid4(), session=session)


# ---------------------------------------------------------------------------
# rename_conversation
# ---------------------------------------------------------------------------


class TestRenameConversation:
    async def test_success(self, service, user_id, mock_ws_row):
        session = AsyncMock()
        conv_id = uuid.uuid4()
        conv = _make_mock_conv(conv_id=conv_id, workspace_id=mock_ws_row.id, user_id=user_id)
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row)
        conv_repo = _mock_conv_repo(conv=conv)

        with _patch_ws_repo(ws_repo), _patch_conv_repo(conv_repo):
            await service.rename_conversation(
                user_id,
                "ws",
                conv_id,
                "Renamed Conversation",
                session,
            )

        conv_repo.get_conversation_for_workspace.assert_awaited_once_with(
            conv_id, mock_ws_row.id, user_id=user_id
        )
        conv_repo.update_title.assert_awaited_once_with(conv_id, "Renamed Conversation")
        session.commit.assert_awaited_once()

    async def test_not_found_raises(self, service, user_id, mock_ws_row):
        session = AsyncMock()
        conv_id = uuid.uuid4()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row)
        conv_repo = _mock_conv_repo(conv=None)

        with _patch_ws_repo(ws_repo), _patch_conv_repo(conv_repo), pytest.raises(NotFoundError):
            await service.rename_conversation(user_id, "ws", conv_id, "New Title", session)

        conv_repo.update_title.assert_not_awaited()

    async def test_workspace_not_found_raises(self, service, user_id):
        session = AsyncMock()
        ws_repo = _mock_ws_repo(ws_row=None)
        conv_repo = _mock_conv_repo(conv=None)

        with _patch_ws_repo(ws_repo), _patch_conv_repo(conv_repo), pytest.raises(NotFoundError):
            await service.rename_conversation(
                user_id, "missing-workspace", uuid.uuid4(), "New Title", session
            )

        conv_repo.get_conversation_for_workspace.assert_not_awaited()


# ---------------------------------------------------------------------------
# stream_agent: error handling in _generate()
# ---------------------------------------------------------------------------


def _make_failing_graph():
    """Build a mock graph whose astream raises after one chunk."""
    from langchain_core.messages import AIMessageChunk

    graph = MagicMock()
    graph.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="ok")]})

    async def _astream(*args, **kwargs):
        yield AIMessageChunk(content="partial"), {"langgraph_node": "agent"}
        raise RuntimeError("provider exploded")

    graph.astream = _astream
    return graph


class TestStreamAgentErrorHandling:
    async def test_error_propagates_from_generate(
        self, service, user_id, mock_ws_row, mock_agent_row
    ):
        """Exception in agent.stream() propagates through _generate()."""
        session = AsyncMock()
        conv = _make_mock_conv(workspace_id=mock_ws_row.id, user_id=user_id)
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=mock_agent_row)
        conv_repo = _mock_conv_repo(conv=conv)

        failing_graph = _make_failing_graph()
        with (
            patch("personal_assistant.core.agent.create_agent", return_value=failing_graph),
            _patch_ws_repo(ws_repo),
            _patch_conv_repo(conv_repo),
        ):
            tokens, _conv_id = await service.stream_agent(
                user_id, "ws", "Bot", "Hello", conversation_id=None, session=session
            )
            with pytest.raises(RuntimeError, match="provider exploded"):
                async for _ in tokens:
                    pass

    async def test_cache_set_attempted_on_stream_error(
        self, service, user_id, mock_ws_row, mock_agent_row, cache
    ):
        """On stream error, _generate() should still attempt to save partial history to cache."""
        session = AsyncMock()
        conv = _make_mock_conv(workspace_id=mock_ws_row.id, user_id=user_id)
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=mock_agent_row)
        conv_repo = _mock_conv_repo(conv=conv)

        failing_graph = _make_failing_graph()
        with (
            patch("personal_assistant.core.agent.create_agent", return_value=failing_graph),
            _patch_ws_repo(ws_repo),
            _patch_conv_repo(conv_repo),
        ):
            tokens, conv_id = await service.stream_agent(
                user_id, "ws", "Bot", "Hello", conversation_id=None, session=session
            )
            with pytest.raises(RuntimeError):
                async for _ in tokens:
                    pass

        # Cache should have the partial history (at minimum the human message)
        cached = await cache.get(user_id, mock_ws_row.id, conv_id)
        assert cached is not None
        assert len(cached) >= 1  # At least the HumanMessage was added


# ---------------------------------------------------------------------------
# Concurrent chat lock
# ---------------------------------------------------------------------------


class TestConcurrentChatLock:
    async def test_concurrent_run_agent_serialized(
        self, service, user_id, mock_ws_row, mock_agent_row, cache
    ):
        """Two concurrent run_agent calls on the same conversation_id are serialized."""
        import asyncio

        session = AsyncMock()
        conv_id = uuid.uuid4()
        conv = _make_mock_conv(conv_id=conv_id, workspace_id=mock_ws_row.id, user_id=user_id)
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=mock_agent_row)
        conv_repo = _mock_conv_repo(conv=conv)

        call_order: list[str] = []
        original_graph = _make_mock_graph("ok")

        async def slow_ainvoke(*args, **kwargs):
            call_order.append("start")
            await asyncio.sleep(0.05)
            call_order.append("end")
            return original_graph.ainvoke.return_value

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(side_effect=slow_ainvoke)

        with (
            patch("personal_assistant.core.agent.create_agent", return_value=mock_graph),
            _patch_ws_repo(ws_repo),
            _patch_conv_repo(conv_repo),
        ):
            await asyncio.gather(
                service.run_agent(
                    user_id, "ws", "Bot", "msg1", conversation_id=conv_id, session=session
                ),
                service.run_agent(
                    user_id, "ws", "Bot", "msg2", conversation_id=conv_id, session=session
                ),
            )

        # Serialized: start-end-start-end (not start-start-end-end)
        assert call_order == ["start", "end", "start", "end"]

    async def test_lock_released_on_error(self, service, user_id, mock_ws_row, mock_agent_row):
        """Lock is released even if run_agent raises."""
        conv_id = uuid.uuid4()
        conv = _make_mock_conv(conv_id=conv_id, workspace_id=mock_ws_row.id, user_id=user_id)
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=mock_agent_row)
        conv_repo = _mock_conv_repo(conv=conv)

        # Graph whose ainvoke raises (not just astream)
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("provider exploded"))
        session = AsyncMock()

        with (
            patch("personal_assistant.core.agent.create_agent", return_value=mock_graph),
            _patch_ws_repo(ws_repo),
            _patch_conv_repo(conv_repo),
        ):
            with pytest.raises(RuntimeError):
                await service.run_agent(
                    user_id, "ws", "Bot", "msg", conversation_id=conv_id, session=session
                )

        # Lock should be released — not locked
        lock = service._get_lock(conv_id)
        assert not lock.locked()

    async def test_no_lock_for_new_conversation(
        self, service, user_id, mock_ws_row, mock_agent_row
    ):
        """No lock contention when conversation_id is None (new conversations)."""
        session = AsyncMock()
        ws_repo = _mock_ws_repo(ws_row=mock_ws_row, agent_row=mock_agent_row)
        new_conv = _make_mock_conv(workspace_id=mock_ws_row.id, user_id=user_id)
        conv_repo = _mock_conv_repo(conv=new_conv)

        mock_graph = _make_mock_graph("ok")
        with (
            patch("personal_assistant.core.agent.create_agent", return_value=mock_graph),
            _patch_ws_repo(ws_repo),
            _patch_conv_repo(conv_repo),
        ):
            _, conv_id = await service.run_agent(
                user_id, "ws", "Bot", "msg", conversation_id=None, session=session
            )

        # No lock should have been created for None conversation_id
        assert conv_id not in service._locks or not service._locks[conv_id].locked()
