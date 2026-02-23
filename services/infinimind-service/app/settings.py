"""Runtime settings for the InfiniMind service.

This module centralizes configuration so runtime behavior is deterministic across
local runs, Docker, and tests.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings with strict defaults for production safety."""

    model_config = SettingsConfigDict(env_prefix="INFINIMIND_", extra="ignore")

    app_name: str = "InfiniMind Service"
    app_env: str = "dev"
    host: str = "0.0.0.0"
    port: int = 8080

    # API token used by OpenClaw bridge plugin and trusted callers.
    api_key: str = Field(default="change-me", min_length=8)
    # Separate admin token for privileged operations like shadow re-embedding.
    admin_api_key: str | None = None

    # Docker-first default path, mounted as a persistent volume.
    data_dir: Path = Path("/var/lib/infinimind")

    # Embedding defaults are pinned for rollout stability.
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-large"
    openai_api_key: str | None = None

    request_timeout_ms: int = 4000


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide settings singleton."""

    return Settings()
