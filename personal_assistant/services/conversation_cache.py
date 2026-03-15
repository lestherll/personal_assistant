"""Conversation history cache.

Provides a pluggable caching layer for conversation message histories so that
repeated requests within a session can skip the database round-trip.

Key schema: ``(user_id, workspace_name, conversation_id)``

Implementations
---------------
- :class:`InMemoryConversationCache` — LRU dict-backed, suitable for single-instance deploys.
  Set ``max_size=0`` for an unbounded cache.

Future backends (implement :class:`ConversationCache`):
- ``RedisConversationCache``
- ``MemcachedConversationCache``
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections import OrderedDict

from langchain_core.messages import BaseMessage

_CacheKey = tuple[uuid.UUID, str, uuid.UUID]


class ConversationCache(ABC):
    """Abstract conversation cache."""

    @abstractmethod
    async def get(
        self,
        user_id: uuid.UUID,
        workspace_name: str,
        conversation_id: uuid.UUID,
    ) -> list[BaseMessage] | None:
        """Return cached messages or ``None`` on a miss."""

    @abstractmethod
    async def set(
        self,
        user_id: uuid.UUID,
        workspace_name: str,
        conversation_id: uuid.UUID,
        messages: list[BaseMessage],
    ) -> None:
        """Store ``messages`` under the given key."""

    @abstractmethod
    async def invalidate(
        self,
        user_id: uuid.UUID,
        workspace_name: str,
        conversation_id: uuid.UUID,
    ) -> None:
        """Remove the entry for the given key (no-op if absent)."""


class InMemoryConversationCache(ConversationCache):
    """LRU in-memory cache backed by :class:`collections.OrderedDict`.

    Args:
        max_size: Maximum number of entries to keep.  ``0`` means unbounded.
    """

    def __init__(self, max_size: int = 256) -> None:
        self._max_size = max_size
        self._store: OrderedDict[_CacheKey, list[BaseMessage]] = OrderedDict()

    def _key(
        self,
        user_id: uuid.UUID,
        workspace_name: str,
        conversation_id: uuid.UUID,
    ) -> _CacheKey:
        return (user_id, workspace_name, conversation_id)

    async def get(
        self,
        user_id: uuid.UUID,
        workspace_name: str,
        conversation_id: uuid.UUID,
    ) -> list[BaseMessage] | None:
        key = self._key(user_id, workspace_name, conversation_id)
        if key not in self._store:
            return None
        # Move to end (most recently used)
        self._store.move_to_end(key)
        return list(self._store[key])

    async def set(
        self,
        user_id: uuid.UUID,
        workspace_name: str,
        conversation_id: uuid.UUID,
        messages: list[BaseMessage],
    ) -> None:
        key = self._key(user_id, workspace_name, conversation_id)
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = list(messages)
        if self._max_size > 0 and len(self._store) > self._max_size:
            self._store.popitem(last=False)  # evict LRU (first item)

    async def invalidate(
        self,
        user_id: uuid.UUID,
        workspace_name: str,
        conversation_id: uuid.UUID,
    ) -> None:
        key = self._key(user_id, workspace_name, conversation_id)
        self._store.pop(key, None)
