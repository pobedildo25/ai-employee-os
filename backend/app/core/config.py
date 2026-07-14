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
    default_llm_model: str = "openai/gpt-4o-mini"
    fallback_llm_model: str = "deepseek/deepseek-chat"
    secondary_fallback_llm_model: str = "openai/gpt-4o-mini"
    heavy_llm_model: str = "anthropic/claude-sonnet-4"
    llm_max_tokens: int = 4096
    llm_heavy_max_tokens: int = 8192

    log_level: str = "INFO"

    memory_enabled: bool = True
    redis_memory_ttl: int = 3600
    qdrant_collection: str = "knowledge"

    skills_enabled: bool = True
    research_online_enabled: bool = True
    research_online_model: str = "perplexity/sonar"

    agency_archive_path: str = "/data/agency_archive"
    agency_archive_watch_enabled: bool = True
    agency_archive_watch_interval_seconds: int = 30
    agency_archive_max_files_per_client: int = 80
    agency_archive_agency_name: str = "NOVA Agency"

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
