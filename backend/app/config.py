"""Application configuration loaded from environment / .env.

Secrets (Neo4j password) are never hardcoded and never shipped to the frontend.
The .env file is git-ignored; only .env.example is versioned.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_HERE = Path(__file__).resolve()
_BACKEND_DIR = _HERE.parents[1]  # backend/
_REPO_ROOT = _HERE.parents[2]  # repository root


class Settings(BaseSettings):
    """Typed settings. Env vars (UPPER_CASE) override .env values."""

    model_config = SettingsConfigDict(
        # Look for .env at the repo root first, then inside backend/.
        env_file=(str(_REPO_ROOT / ".env"), str(_BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "change-me"
    neo4j_database: str = "neo4j"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma4:e4b"

    # When true, use the deterministic in-process mock instead of Ollama.
    mock_llm: bool = True

    # CORS (comma-separated origins)
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
