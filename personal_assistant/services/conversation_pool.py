from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from personal_assistant.core.agent import Agent


@dataclass
class PoolEntry:
    agent: Agent
    last_accessed: float = 0.0


class ConversationPool:
    """In-memory pool of per-conversation Agent clones.

    Key: (workspace_name, agent_name, conversation_id)
    Evicts the LRU entry when max_size is reached and expired entries on demand.
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 7200.0) -> None:
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._store: dict[tuple[str, str, uuid.UUID], PoolEntry] = {}

    def get(self, workspace_name: str, agent_name: str, conversation_id: uuid.UUID) -> Agent | None:
        key = (workspace_name, agent_name, conversation_id)
        entry = self._store.get(key)
        if entry is None:
            return None
        entry.last_accessed = time.monotonic()
        return entry.agent

    def put(
        self,
        workspace_name: str,
        agent_name: str,
        conversation_id: uuid.UUID,
        agent: Agent,
    ) -> None:
        key = (workspace_name, agent_name, conversation_id)
        now = time.monotonic()
        if key in self._store:
            self._store[key].agent = agent
            self._store[key].last_accessed = now
            return
        if len(self._store) >= self._max_size:
            lru_key = min(self._store, key=lambda k: self._store[k].last_accessed)
            del self._store[lru_key]
        self._store[key] = PoolEntry(agent=agent, last_accessed=now)

    def evict(self, workspace_name: str, agent_name: str, conversation_id: uuid.UUID) -> None:
        self._store.pop((workspace_name, agent_name, conversation_id), None)

    def evict_expired(self) -> int:
        """Remove all entries older than ttl_seconds. Returns count removed."""
        now = time.monotonic()
        expired = [k for k, v in self._store.items() if now - v.last_accessed > self._ttl]
        for k in expired:
            del self._store[k]
        return len(expired)
