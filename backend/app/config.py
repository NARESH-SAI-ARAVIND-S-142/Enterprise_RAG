"""
DocuMind 2.0 — Application Configuration
Pydantic Settings loaded from environment variables / .env file.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── LLM Providers ──────────────────────────────────────────
    GROQ_API_KEY: str = Field(default="", description="Groq API key for LLM access")
    ANTHROPIC_API_KEY: str = Field(default="", description="Anthropic API key (Claude fallback)")

    # ── Vector Database ────────────────────────────────────────
    QDRANT_URL: str = Field(default="http://localhost:6333", description="Qdrant server URL")
    QDRANT_API_KEY: str = Field(default="", description="Qdrant API key (empty for local)")

    # ── Database ───────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./documind.db",
        description="SQLAlchemy async database URL",
    )

    # ── Redis / Celery ─────────────────────────────────────────
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")

    # ── Authentication ─────────────────────────────────────────
    SECRET_KEY: str = Field(
        default="CHANGE-THIS-TO-A-VERY-LONG-RANDOM-SECRET-KEY-MIN-32-CHARS",
        description="JWT signing secret key",
    )
    ACCESS_TOKEN_EXPIRE_HOURS: int = Field(default=24, description="Access token TTL in hours")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, description="Refresh token TTL in days")

    # ── Observability ──────────────────────────────────────────
    LANGCHAIN_TRACING_V2: bool = Field(default=True, description="Enable LangSmith tracing")
    LANGCHAIN_API_KEY: str = Field(default="", description="LangSmith API key")
    LANGCHAIN_PROJECT: str = Field(default="documind-production", description="LangSmith project name")

    # ── Storage ────────────────────────────────────────────────
    UPLOAD_DIR: str = Field(default="/uploads", description="Directory for uploaded files")
    MAX_UPLOAD_SIZE_MB: int = Field(default=50, description="Maximum upload file size in MB")

    # ── Evaluation ─────────────────────────────────────────────
    RAGAS_EVAL_ENABLED: bool = Field(default=True, description="Enable RAGAS evaluation")
    RAGAS_FAITHFULNESS_THRESHOLD: float = Field(
        default=0.8, description="Minimum faithfulness score threshold"
    )

    # ── Embedding Model ────────────────────────────────────────
    EMBEDDING_MODEL_NAME: str = Field(
        default="all-MiniLM-L6-v2", description="HuggingFace embedding model"
    )
    EMBEDDING_DIMENSION: int = Field(default=384, description="Embedding vector dimension")

    # ── Cross Encoder ──────────────────────────────────────────
    CROSS_ENCODER_MODEL: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-12-v2",
        description="CrossEncoder model for reranking",
    )

    # ── Default LLM ────────────────────────────────────────────
    DEFAULT_LLM_MODEL: str = Field(
        default="llama-3.1-8b-instant", description="Default LLM model name"
    )
    DEFAULT_LLM_PROVIDER: str = Field(default="groq", description="Default LLM provider")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance — loaded once at startup."""
    return Settings()


settings = get_settings()
