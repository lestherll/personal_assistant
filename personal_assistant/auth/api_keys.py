"""API key generation, hashing, and verification.

Uses SHA-256 (not Argon2) because API keys are high-entropy random tokens,
so brute-force resistance from a slow hash is unnecessary. Comparison uses
hmac.compare_digest to prevent timing attacks.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_PREFIX = "sk-"


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key. Returns (raw_key, sha256_hash)."""
    raw = _PREFIX + secrets.token_urlsafe(32)
    return raw, hash_api_key(raw)


def hash_api_key(key: str) -> str:
    """Return the SHA-256 hex digest of an API key."""
    return hashlib.sha256(key.encode()).hexdigest()


def verify_api_key(key: str, key_hash: str) -> bool:
    """Constant-time comparison of a raw key against a stored hash."""
    return hmac.compare_digest(hash_api_key(key), key_hash)
