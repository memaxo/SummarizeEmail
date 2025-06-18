import logging
import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings for the Email Summarizer API.
    
    Utilizes pydantic-settings for robust parsing and type-checking.
    Environment variables are loaded from the .env file.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # LLM Provider Configuration
    LLM_PROVIDER: str = "gemini"  # Changed default to gemini
    
    # OpenAI Configuration
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL_NAME: str = "gpt-4o-mini"
    
    # Google Gemini Configuration
    GOOGLE_API_KEY: Optional[str] = None  # For simple API key auth
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None  # Path to service account JSON
    GOOGLE_CLOUD_PROJECT: Optional[str] = None  # GCP project ID
    GOOGLE_CLOUD_LOCATION: str = "us-central1"  # Vertex AI location
    GEMINI_MODEL_NAME: str = "gemini-2.5-flash"  # Back to the newer model
    
    # Ollama Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama2"
    
    # Microsoft Graph API Configuration
    AZURE_CLIENT_ID: Optional[str] = None
    AZURE_CLIENT_SECRET: Optional[str] = None
    AZURE_TENANT_ID: Optional[str] = None
    AZURE_REDIRECT_URI: str = "http://localhost:8000/auth/callback"
    
    # API Configuration
    API_TITLE: str = "Email Summarizer API"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "An API to summarize emails using LangChain."
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database
    DATABASE_URL: str = "postgresql://emailsummarizer:password123@localhost:5432/emailsummarizer"
    
    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_EXPIRATION_SECONDS: int = 3600  # 1 hour
    
    # Celery Configuration
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"
    
    # CORS
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8000"]
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_TIMESCALE: str = "minute"
    
    # Target user ID for email fetching (development only)
    TARGET_USER_ID: str = "me"
    
    # Mock API Configuration (for testing)
    USE_MOCK_GRAPH_API: bool = False
    MOCK_GRAPH_API_URL: str = "http://localhost:8001"
    
    # RAG Configuration
    RAG_INGESTION_INTERVAL_HOURS: int = 24  # How often to ingest emails for RAG
    RAG_TOKEN_MAX: int = 16000  # Maximum tokens for RAG chain (safety net for Gemini's 30k context)
    
    # --- RAG tokenisation helpers ---
    # Context-window sizes for supported chat models
    MODEL_CONTEXT_WINDOWS: dict = {
        "gemini-2.5-flash": 1_048_576,
        "gpt-4o-mini": 128_000,
        "gpt-4.1": 1_000_000,
    }
    # Recommended chunk ≈ 2 % of context window (hard-capped below)
    CHUNK_SIZE_RATIO: float = 0.02
    DEFAULT_CHUNK_OVERLAP: int = 200


@lru_cache()
def get_settings() -> Settings:
    """
    Returns the application settings instance.
    Uses lru_cache to ensure settings are loaded only once.
    """
    # Logging is centrally configured in app.logger
    logging.getLogger(__name__).info("Loading application settings...")
    return Settings()


settings = get_settings()

# Validate that necessary credentials are provided based on the LLM_PROVIDER
if settings.LLM_PROVIDER == "openai" and not settings.OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY must be set when LLM_PROVIDER is 'openai'")
elif settings.LLM_PROVIDER == "gemini":
    # Check for either API key or service account credentials
    if not settings.GOOGLE_API_KEY and not (settings.GOOGLE_APPLICATION_CREDENTIALS and settings.GOOGLE_CLOUD_PROJECT):
        raise ValueError(
            "Either GOOGLE_API_KEY or both GOOGLE_APPLICATION_CREDENTIALS and GOOGLE_CLOUD_PROJECT "
            "must be set when LLM_PROVIDER is 'gemini'"
        ) 