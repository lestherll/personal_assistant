from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Auth / JWT
    secret_key: str = "change-me-in-production-32-plus-bytes"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    auth_disabled: bool = False

    # Persistence
    database_url: str | None = None

    # Providers
    anthropic_api_key: str | None = None

    # Tools
    rapidapi_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
