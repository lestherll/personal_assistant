from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import jwt
from jwt.exceptions import InvalidTokenError

from personal_assistant.services.exceptions import AuthError

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def create_access_token(sub: str) -> str:
    """Create a short-lived access token."""
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": sub, "type": "access", "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(sub: str) -> str:
    """Create a long-lived refresh token."""
    expire = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": sub, "type": "refresh", "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, object]:
    """Decode and verify a JWT token. Raises AuthError on failure."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except InvalidTokenError as exc:
        raise AuthError(str(exc)) from exc
