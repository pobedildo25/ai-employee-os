from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str = "change-me"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "postgresql+asyncpg://ai_employee:change-me@localhost:5432/ai_employee_os"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_bucket: str = "artifacts"

    openrouter_api_key: str = "change-me"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    default_llm_model: str = "deepseek/deepseek-chat"
    fallback_llm_model: str = "anthropic/claude-sonnet-4"
    secondary_fallback_llm_model: str = "openai/gpt-4o-mini"

    log_level: str = "INFO"

    memory_enabled: bool = True
    redis_memory_ttl: int = 3600
    qdrant_collection: str = "knowledge"

    # Semantic-memory embeddings. Off by default → deterministic stub vectors.
    # When enabled, semantic memory uses a real embedding model via the LLM gateway.
    embeddings_enabled: bool = False
    embedding_model: str = "openai/text-embedding-3-small"
    embedding_dimensions: int = 1536

    # --- Multimodal input (Phase B) ---
    # Vision uses the same OpenRouter key with a multimodal model.
    vision_enabled: bool = True
    vision_model: str = "openai/gpt-4o-mini"
    # Audio transcription needs a Whisper-compatible endpoint (OpenRouter has none),
    # so it is opt-in and configured separately. Falls back to OPENROUTER_API_KEY only
    # when the transcription base_url points at a compatible service.
    transcription_enabled: bool = False
    transcription_base_url: str = "https://api.openai.com/v1"
    transcription_api_key: str = ""
    transcription_model: str = "whisper-1"
    # Max characters of extracted attachment text injected into the model context.
    attachment_max_chars: int = 6000

    skills_enabled: bool = True

    # Agency identity ("who WE are") — injected into dialogue and every document
    # so the assistant speaks and writes as an employee of THIS agency.
    agency_name: str = "NOVA"
    agency_tagline: str = ""
    agency_positioning: str = ""
    agency_services: str = ""  # comma/newline separated list
    agency_tone: str = ""
    agency_requisites: str = ""
    agency_contacts: str = ""
    agency_website: str = ""
    agency_profile_json: str = ""  # optional full JSON override

    telegram_bot_token: str = ""
    telegram_enabled: bool = False

    security_enabled: bool = False
    security_rate_limit: int = 120
    security_rate_window_seconds: int = 60

    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800
    run_migrations_on_startup: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
