from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from jwt.exceptions import InvalidTokenError

from personal_assistant.config import get_settings
from personal_assistant.services.exceptions import AuthError

ALGORITHM = "HS256"


def create_access_token(sub: str) -> str:
    """Create a short-lived access token."""
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": sub, "type": "access", "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token(sub: str) -> str:
    """Create a long-lived refresh token."""
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    payload = {"sub": sub, "type": "refresh", "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, object]:
    """Decode and verify a JWT token. Raises AuthError on failure."""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except InvalidTokenError as exc:
        raise AuthError(str(exc)) from exc
