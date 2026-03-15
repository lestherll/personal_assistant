"""Tests for ConversationCache and InMemoryConversationCache."""

import uuid

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from personal_assistant.services.conversation_cache import InMemoryConversationCache


@pytest.fixture
def cache() -> InMemoryConversationCache:
    return InMemoryConversationCache(max_size=3)


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def messages():
    return [HumanMessage(content="hello"), AIMessage(content="hi")]


# ---------------------------------------------------------------------------
# get / set / invalidate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_none_when_empty(cache, user_id):
    result = await cache.get(user_id, "ws", uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_set_then_get_returns_messages(cache, user_id, messages):
    conv_id = uuid.uuid4()
    await cache.set(user_id, "ws", conv_id, messages)
    result = await cache.get(user_id, "ws", conv_id)
    assert result is not None
    assert len(result) == 2
    assert result[0].content == "hello"
    assert result[1].content == "hi"


@pytest.mark.asyncio
async def test_get_returns_copy_not_reference(cache, user_id, messages):
    """Mutating the returned list must not affect the cache."""
    conv_id = uuid.uuid4()
    await cache.set(user_id, "ws", conv_id, messages)
    result = await cache.get(user_id, "ws", conv_id)
    assert result is not None
    result.append(HumanMessage(content="extra"))
    still_cached = await cache.get(user_id, "ws", conv_id)
    assert still_cached is not None
    assert len(still_cached) == 2


@pytest.mark.asyncio
async def test_invalidate_removes_entry(cache, user_id, messages):
    conv_id = uuid.uuid4()
    await cache.set(user_id, "ws", conv_id, messages)
    await cache.invalidate(user_id, "ws", conv_id)
    assert await cache.get(user_id, "ws", conv_id) is None


@pytest.mark.asyncio
async def test_invalidate_missing_key_is_noop(cache, user_id):
    """Invalidating a key that doesn't exist should not raise."""
    await cache.invalidate(user_id, "ws", uuid.uuid4())


# ---------------------------------------------------------------------------
# Key isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_different_users_are_isolated(cache, messages):
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    conv_id = uuid.uuid4()
    await cache.set(user_a, "ws", conv_id, messages)
    assert await cache.get(user_a, "ws", conv_id) is not None
    assert await cache.get(user_b, "ws", conv_id) is None


@pytest.mark.asyncio
async def test_different_workspaces_are_isolated(cache, user_id, messages):
    conv_id = uuid.uuid4()
    await cache.set(user_id, "ws1", conv_id, messages)
    assert await cache.get(user_id, "ws1", conv_id) is not None
    assert await cache.get(user_id, "ws2", conv_id) is None


@pytest.mark.asyncio
async def test_different_conv_ids_are_isolated(cache, user_id, messages):
    conv_a = uuid.uuid4()
    conv_b = uuid.uuid4()
    await cache.set(user_id, "ws", conv_a, messages)
    assert await cache.get(user_id, "ws", conv_a) is not None
    assert await cache.get(user_id, "ws", conv_b) is None


# ---------------------------------------------------------------------------
# LRU eviction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lru_eviction_removes_oldest(cache, user_id, messages):
    """With max_size=3, inserting a 4th entry evicts the LRU entry."""
    ids = [uuid.uuid4() for _ in range(4)]
    for i in range(3):
        await cache.set(user_id, "ws", ids[i], messages)

    # Access ids[0] to make it recently used
    await cache.get(user_id, "ws", ids[0])

    # Insert a 4th entry — ids[1] should be evicted (LRU)
    await cache.set(user_id, "ws", ids[3], messages)

    assert await cache.get(user_id, "ws", ids[0]) is not None  # recently used, kept
    assert await cache.get(user_id, "ws", ids[1]) is None  # LRU, evicted
    assert await cache.get(user_id, "ws", ids[2]) is not None
    assert await cache.get(user_id, "ws", ids[3]) is not None


@pytest.mark.asyncio
async def test_no_eviction_when_size_not_exceeded(cache, user_id, messages):
    ids = [uuid.uuid4() for _ in range(3)]
    for i in range(3):
        await cache.set(user_id, "ws", ids[i], messages)
    for i in range(3):
        assert await cache.get(user_id, "ws", ids[i]) is not None


@pytest.mark.asyncio
async def test_unbounded_cache(user_id, messages):
    """max_size=0 means no eviction."""
    cache = InMemoryConversationCache(max_size=0)
    ids = [uuid.uuid4() for _ in range(100)]
    for conv_id in ids:
        await cache.set(user_id, "ws", conv_id, messages)
    for conv_id in ids:
        assert await cache.get(user_id, "ws", conv_id) is not None
