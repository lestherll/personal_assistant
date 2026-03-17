"""Per-user rate limiting for chat endpoints.

Uses a fixed-window algorithm with an in-memory dict. Each user gets
`max_requests` calls per `window_seconds`.
"""

from __future__ import annotations

import math
import time
import uuid

from fastapi import HTTPException, status


class RateLimiter:
    """Fixed-window per-user rate limiter."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: dict[uuid.UUID, tuple[int, float]] = {}

    def check(self, user_id: uuid.UUID) -> None:
        """Raise HTTP 429 if the user has exceeded their rate limit."""
        now = time.monotonic()
        count, window_start = self._windows.get(user_id, (0, now))

        if now - window_start >= self.window_seconds:
            # Window expired — reset
            count = 0
            window_start = now

        count += 1
        self._windows[user_id] = (count, window_start)

        if count > self.max_requests:
            retry_after = math.ceil(self.window_seconds - (now - window_start))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(max(1, retry_after))},
            )
