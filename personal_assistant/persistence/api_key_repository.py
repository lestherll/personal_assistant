"""Data-access layer for UserAPIKey records."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from personal_assistant.persistence.models import UserAPIKey


class APIKeyRepository:
    """CRUD operations for API keys."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: uuid.UUID,
        name: str,
        key_hash: str,
        key_prefix: str,
        *,
        expires_at: datetime | None = None,
    ) -> UserAPIKey:
        row = UserAPIKey(
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            expires_at=expires_at,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def get_by_hash(self, key_hash: str) -> UserAPIKey | None:
        result = await self._session.execute(
            select(UserAPIKey).where(UserAPIKey.key_hash == key_hash)
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[UserAPIKey]:
        result = await self._session.execute(
            select(UserAPIKey)
            .where(UserAPIKey.user_id == user_id)
            .order_by(UserAPIKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def revoke(self, user_id: uuid.UUID, key_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            update(UserAPIKey)
            .where(UserAPIKey.id == key_id, UserAPIKey.user_id == user_id)
            .values(is_active=False)
        )
        await self._session.flush()
        return result.rowcount > 0  # type: ignore

    async def rotate(
        self,
        user_id: uuid.UUID,
        key_id: uuid.UUID,
        *,
        new_key_hash: str,
        new_key_prefix: str,
    ) -> UserAPIKey | None:
        result = await self._session.execute(
            select(UserAPIKey)
            .where(
                UserAPIKey.id == key_id,
                UserAPIKey.user_id == user_id,
                UserAPIKey.is_active.is_(True),
            )
            .with_for_update()
        )
        current = result.scalar_one_or_none()
        if current is None:
            return None

        current.is_active = False
        row = UserAPIKey(
            user_id=current.user_id,
            name=current.name,
            key_hash=new_key_hash,
            key_prefix=new_key_prefix,
            expires_at=current.expires_at,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def update_last_used(self, key_id: uuid.UUID, now: datetime) -> None:
        await self._session.execute(
            update(UserAPIKey).where(UserAPIKey.id == key_id).values(last_used_at=now)
        )
        await self._session.flush()
