"""Unit tests for persistence/database.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from personal_assistant.persistence.database import build_engine, build_session_factory


class TestBuildEngine:
    def test_build_engine_returns_async_engine(self):
        mock_engine = MagicMock(spec=AsyncEngine)
        with patch(
            "personal_assistant.persistence.database.create_async_engine",
            return_value=mock_engine,
        ) as mock_create:
            engine = build_engine("postgresql+asyncpg://user:pass@localhost/db")
        assert engine is mock_engine
        mock_create.assert_called_once_with(
            "postgresql+asyncpg://user:pass@localhost/db",
            echo=False,
            pool_pre_ping=True,
        )

    def test_build_engine_sets_pool_pre_ping(self):
        with patch(
            "personal_assistant.persistence.database.create_async_engine",
            return_value=MagicMock(spec=AsyncEngine),
        ) as mock_create:
            build_engine("postgresql+asyncpg://user:pass@localhost/db")
        _, kwargs = mock_create.call_args
        assert kwargs["pool_pre_ping"] is True


class TestBuildSessionFactory:
    def test_build_session_factory_uses_engine(self):
        mock_engine = MagicMock(spec=AsyncEngine)
        mock_factory = MagicMock(spec=async_sessionmaker)
        with patch(
            "personal_assistant.persistence.database.async_sessionmaker",
            return_value=mock_factory,
        ) as mock_maker:
            factory = build_session_factory(mock_engine)
        assert factory is mock_factory
        mock_maker.assert_called_once_with(mock_engine, class_=AsyncSession, expire_on_commit=False)

    def test_build_session_factory_sets_expire_on_commit_false(self):
        mock_engine = MagicMock(spec=AsyncEngine)
        with patch(
            "personal_assistant.persistence.database.async_sessionmaker",
            return_value=MagicMock(),
        ) as mock_maker:
            build_session_factory(mock_engine)
        _, kwargs = mock_maker.call_args
        assert kwargs["expire_on_commit"] is False
