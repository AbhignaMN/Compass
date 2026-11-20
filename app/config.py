"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized settings so models, DB URL, and ranking weights live in one place."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "Compass"
    app_version: str = "0.1.0"
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Database
    database_url: str = "postgresql+asyncpg://compass:compass@localhost:5432/compass"

    # LLM (Anthropic Claude) — single config variable for model switching
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    claude_memory_model: str = "claude-haiku-4-5-20251001"
    agent_max_iterations: int = 6

    # Local embeddings (fastembed)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    embedding_cache_dir: str = ".fastembed_cache"

    # Hybrid search & ranking weights
    rrf_k: int = 60
    rank_weight_semantic: float = Field(default=0.50, ge=0.0, le=1.0)
    rank_weight_skill_overlap: float = Field(default=0.25, ge=0.0, le=1.0)
    rank_weight_preference_fit: float = Field(default=0.15, ge=0.0, le=1.0)
    rank_weight_freshness: float = Field(default=0.10, ge=0.0, le=1.0)

    # Rate limits
    rate_limit_chat: str = "30/minute"
    rate_limit_default: str = "120/minute"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
