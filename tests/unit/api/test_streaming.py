"""Tests for the shared SSE event generator."""

from __future__ import annotations

from collections.abc import AsyncIterator

from api.streaming import sse_event_generator


async def _tokens(*values: str) -> AsyncIterator[str]:
    """Helper that yields the given strings as an async iterator."""
    for v in values:
        yield v


async def _failing_tokens(*values: str) -> AsyncIterator[str]:
    """Yield some tokens then raise an exception."""
    for v in values:
        yield v
    raise RuntimeError("provider exploded")


async def _collect(gen: AsyncIterator[str]) -> list[str]:
    """Drain an async iterator into a list."""
    return [item async for item in gen]


class TestSseEventGenerator:
    async def test_emits_done_on_clean_completion(self) -> None:
        result = await _collect(sse_event_generator(_tokens("hello", " world")))

        assert result == ["data: hello\n\n", "data:  world\n\n", "data: [DONE]\n\n"]

    async def test_emits_error_on_exception(self) -> None:
        result = await _collect(sse_event_generator(_failing_tokens("partial")))

        assert "data: partial\n\n" in result
        assert "data: [ERROR]\n\n" in result

    async def test_no_done_after_error(self) -> None:
        result = await _collect(sse_event_generator(_failing_tokens("partial")))

        assert "data: [DONE]\n\n" not in result

    async def test_error_on_empty_stream_failure(self) -> None:
        """Exception before any tokens are yielded."""
        result = await _collect(sse_event_generator(_failing_tokens()))

        assert result == ["data: [ERROR]\n\n"]

    async def test_empty_stream_success(self) -> None:
        """No tokens yielded, clean completion."""
        result = await _collect(sse_event_generator(_tokens()))

        assert result == ["data: [DONE]\n\n"]
