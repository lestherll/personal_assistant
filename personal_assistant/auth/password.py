from __future__ import annotations

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()


def hash_password(plain: str) -> str:
    """Hash a plain-text password using Argon2."""
    return _password_hash.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a stored hash."""
    return _password_hash.verify(plain, hashed)
