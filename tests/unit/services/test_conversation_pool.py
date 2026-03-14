"""Unit tests for ConversationPool."""

from __future__ import annotations

import time
import uuid
from unittest.mock import MagicMock

from personal_assistant.services.conversation_pool import ConversationPool


def _make_agent() -> MagicMock:
    return MagicMock()


WS = "default"
AGENT = "assistant"


class TestConversationPoolGet:
    def test_miss_returns_none(self):
        pool = ConversationPool()
        assert pool.get(WS, AGENT, uuid.uuid4()) is None

    def test_hit_returns_agent(self):
        pool = ConversationPool()
        cid = uuid.uuid4()
        agent = _make_agent()
        pool.put(WS, AGENT, cid, agent)
        assert pool.get(WS, AGENT, cid) is agent

    def test_different_keys_do_not_collide(self):
        pool = ConversationPool()
        cid1, cid2 = uuid.uuid4(), uuid.uuid4()
        a1, a2 = _make_agent(), _make_agent()
        pool.put(WS, AGENT, cid1, a1)
        pool.put(WS, AGENT, cid2, a2)
        assert pool.get(WS, AGENT, cid1) is a1
        assert pool.get(WS, AGENT, cid2) is a2


class TestConversationPoolPut:
    def test_put_updates_existing_entry(self):
        pool = ConversationPool()
        cid = uuid.uuid4()
        a1, a2 = _make_agent(), _make_agent()
        pool.put(WS, AGENT, cid, a1)
        pool.put(WS, AGENT, cid, a2)
        assert pool.get(WS, AGENT, cid) is a2

    def test_lru_eviction_at_max_size(self):
        pool = ConversationPool(max_size=2)
        cid1, cid2, cid3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        a1, a2, a3 = _make_agent(), _make_agent(), _make_agent()
        pool.put(WS, AGENT, cid1, a1)
        pool.put(WS, AGENT, cid2, a2)
        # Access cid1 so cid2 becomes LRU
        pool.get(WS, AGENT, cid1)
        pool.put(WS, AGENT, cid3, a3)
        # cid2 should have been evicted (LRU)
        assert pool.get(WS, AGENT, cid2) is None
        assert pool.get(WS, AGENT, cid1) is a1
        assert pool.get(WS, AGENT, cid3) is a3


class TestConversationPoolEvict:
    def test_evict_removes_entry(self):
        pool = ConversationPool()
        cid = uuid.uuid4()
        pool.put(WS, AGENT, cid, _make_agent())
        pool.evict(WS, AGENT, cid)
        assert pool.get(WS, AGENT, cid) is None

    def test_evict_missing_key_is_noop(self):
        pool = ConversationPool()
        pool.evict(WS, AGENT, uuid.uuid4())  # should not raise


class TestConversationPoolEvictExpired:
    def test_removes_expired_entries(self, monkeypatch):
        pool = ConversationPool(ttl_seconds=10.0)
        cid_old = uuid.uuid4()
        cid_new = uuid.uuid4()
        a1, a2 = _make_agent(), _make_agent()

        start = time.monotonic()
        monkeypatch.setattr(time, "monotonic", lambda: start)
        pool.put(WS, AGENT, cid_old, a1)

        monkeypatch.setattr(time, "monotonic", lambda: start + 5)
        pool.put(WS, AGENT, cid_new, a2)

        # Advance clock past TTL of cid_old but not cid_new
        monkeypatch.setattr(time, "monotonic", lambda: start + 11)
        count = pool.evict_expired()

        assert count == 1
        assert pool.get(WS, AGENT, cid_old) is None
        assert pool.get(WS, AGENT, cid_new) is not None

    def test_returns_zero_when_nothing_expired(self):
        pool = ConversationPool(ttl_seconds=3600.0)
        pool.put(WS, AGENT, uuid.uuid4(), _make_agent())
        assert pool.evict_expired() == 0
