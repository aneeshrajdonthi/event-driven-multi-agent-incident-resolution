"""Application configuration via Pydantic BaseSettings."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration loaded from environment variables / .env file."""

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"

    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "incidents"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # vLLM (OpenAI-compatible endpoint)
    VLLM_API_URL: str = "http://localhost:8001/v1"

    # Google Gemini
    GEMINI_API_KEY: str = ""

    # Model selection
    MODEL_NAME: str = "mistral-7b"
    LORA_ADAPTER_PATH: str = ""

    # Observability
    LOG_LEVEL: str = "INFO"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of application settings."""
    return Settings()
