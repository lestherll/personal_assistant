"""Tests for per-user rate limiting."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from api.rate_limit import RateLimiter


@pytest.fixture
def limiter() -> RateLimiter:
    return RateLimiter(max_requests=3, window_seconds=60)


class TestRateLimiter:
    def test_under_limit_passes(self, limiter: RateLimiter) -> None:
        uid = uuid.uuid4()
        # Should not raise
        limiter.check(uid)
        limiter.check(uid)
        limiter.check(uid)

    def test_over_limit_raises_429(self, limiter: RateLimiter) -> None:
        uid = uuid.uuid4()
        limiter.check(uid)
        limiter.check(uid)
        limiter.check(uid)
        with pytest.raises(HTTPException) as exc_info:
            limiter.check(uid)
        assert exc_info.value.status_code == 429
        assert "Retry-After" in exc_info.value.headers

    def test_different_users_have_separate_limits(self, limiter: RateLimiter) -> None:
        uid_a = uuid.uuid4()
        uid_b = uuid.uuid4()
        for _ in range(3):
            limiter.check(uid_a)
        # uid_b should still be under limit
        limiter.check(uid_b)

    def test_window_reset_allows_new_requests(self) -> None:
        import time

        limiter = RateLimiter(max_requests=1, window_seconds=0.1)
        uid = uuid.uuid4()
        limiter.check(uid)
        # Should be over limit
        with pytest.raises(HTTPException):
            limiter.check(uid)
        # Wait for window to expire
        time.sleep(0.15)
        # Should work again
        limiter.check(uid)

    def test_retry_after_header_value(self, limiter: RateLimiter) -> None:
        uid = uuid.uuid4()
        for _ in range(3):
            limiter.check(uid)
        with pytest.raises(HTTPException) as exc_info:
            limiter.check(uid)
        retry_after = int(exc_info.value.headers["Retry-After"])
        assert 0 < retry_after <= 60
