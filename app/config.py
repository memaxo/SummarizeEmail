import logging
import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Loads and validates application settings from environment variables.
    Utilizes pydantic-settings for robust parsing and type-checking.
    """
    # Azure AD App Registration Details
    TENANT_ID: str
    CLIENT_ID: str
    CLIENT_SECRET: str
    TARGET_USER_ID: str

    # LLM Provider Configuration
    LLM_PROVIDER: str = "openai"

    # OpenAI Configuration
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL_NAME: str = "gpt-4o-mini"

    # Ollama Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"

    # Redis Cache Configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600  # seconds

    # API Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_TIMESCALE: str = "minute"

    # Load settings from a .env file
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), '..', '.env'),
        env_file_encoding='utf-8',
        extra='ignore'
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Returns the application settings instance.
    Uses lru_cache to ensure settings are loaded only once.
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logging.info("Loading application settings...")
    return Settings()


settings = get_settings()

# Validate that necessary credentials are provided based on the LLM_PROVIDER
if settings.LLM_PROVIDER == "openai" and not settings.OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY must be set when LLM_PROVIDER is 'openai'") 