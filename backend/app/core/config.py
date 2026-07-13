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

    skills_enabled: bool = True

    telegram_bot_token: str = ""
    telegram_enabled: bool = False
    telegram_allowed_user_ids: str = ""

    security_enabled: bool = False
    security_rate_limit: int = 120
    security_rate_window_seconds: int = 60

    research_enabled: bool = False
    semantic_memory_enabled: bool = False

    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800
    run_migrations_on_startup: bool = False

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    def parsed_telegram_allowed_user_ids(self) -> set[int]:
        raw = (self.telegram_allowed_user_ids or "").strip()
        if not raw:
            return set()
        result: set[int] = set()
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                result.add(int(part))
            except ValueError:
                continue
        return result


@lru_cache
def get_settings() -> Settings:
    return Settings()
