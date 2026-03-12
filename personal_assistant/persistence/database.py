from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def build_engine(database_url: str) -> AsyncEngine:
    """Create an async SQLAlchemy engine from a DATABASE_URL.

    The URL should use the ``postgresql+asyncpg://`` scheme, e.g.::

        postgresql+asyncpg://user:password@localhost:5432/personal_assistant
    """
    return create_async_engine(database_url, echo=False, pool_pre_ping=True)


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return a session factory bound to *engine*."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
