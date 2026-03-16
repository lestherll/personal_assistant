"""Shared SSE streaming utilities for FastAPI routers."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


async def sse_event_generator(token_iter: AsyncIterator[str]) -> AsyncIterator[str]:
    """Wrap a token iterator with SSE framing, error sentinel, and done sentinel.

    Yields ``data: {token}\\n\\n`` for each token. On clean completion emits
    ``data: [DONE]\\n\\n``. If the underlying iterator raises, emits
    ``data: [ERROR]\\n\\n`` instead (no ``[DONE]`` follows an ``[ERROR]``).
    """
    try:
        async for token in token_iter:
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"
    except Exception:
        logger.exception("SSE stream error")
        yield "data: [ERROR]\n\n"
