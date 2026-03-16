"""Tests for API key generation, hashing, and verification."""

from __future__ import annotations

from personal_assistant.auth.api_keys import generate_api_key, hash_api_key, verify_api_key


class TestGenerateApiKey:
    def test_starts_with_sk_prefix(self):
        raw, _hash = generate_api_key()
        assert raw.startswith("sk-")

    def test_returns_different_keys(self):
        raw1, _ = generate_api_key()
        raw2, _ = generate_api_key()
        assert raw1 != raw2

    def test_returns_hash(self):
        raw, key_hash = generate_api_key()
        assert key_hash
        assert key_hash != raw


class TestHashApiKey:
    def test_deterministic(self):
        h1 = hash_api_key("sk-abc123")
        h2 = hash_api_key("sk-abc123")
        assert h1 == h2

    def test_different_keys_different_hashes(self):
        h1 = hash_api_key("sk-abc123")
        h2 = hash_api_key("sk-xyz789")
        assert h1 != h2


class TestVerifyApiKey:
    def test_valid_key(self):
        raw, key_hash = generate_api_key()
        assert verify_api_key(raw, key_hash) is True

    def test_wrong_key(self):
        _, key_hash = generate_api_key()
        assert verify_api_key("sk-wrong", key_hash) is False

    def test_tampered_hash(self):
        raw, _ = generate_api_key()
        assert verify_api_key(raw, "tampered") is False
