from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_BACKEND_DIR = Path(__file__).resolve().parents[1]
_DEFAULT_DB_URL = f"sqlite:///{_BACKEND_DIR / 'edgematch.db'}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "EdgeMatch MVP"
    demo_mode: bool = False
    database_url: str = _DEFAULT_DB_URL

    crustdata_base_url: str = "https://api.crustdata.com"
    crustdata_token: str | None = None
    crustdata_auth_scheme: Literal["auto", "token", "bearer"] = "auto"
    crustdata_timeout_seconds: float = 12.0
    crustdata_cache_ttl_seconds: int = 90

    openai_api_key: str | None = None
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    @field_validator("crustdata_cache_ttl_seconds")
    @classmethod
    def _clamp_cache_ttl(cls, value: int) -> int:
        return max(60, min(120, value))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
