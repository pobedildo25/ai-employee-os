import re
from typing import Any

from app.core.config import Settings, get_settings

_SECRET_PATTERNS = [
    re.compile(r"(api[_-]?key\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE),
    re.compile(r"(token\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE),
    re.compile(r"(bearer\s+)([^\s,;]+)", re.IGNORECASE),
    re.compile(r"(password\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE),
    re.compile(r"(secret\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE),
    re.compile(r"\baeo_[A-Za-z0-9_\-]{16,}\b"),
]


class SecretsManager:
    """Reads configured secrets and redacts them from log-like strings."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def get(self, name: str, default: str | None = None) -> str | None:
        mapping = {
            "app_secret_key": self._settings.app_secret_key,
            "openrouter_api_key": self._settings.openrouter_api_key,
            "telegram_bot_token": self._settings.telegram_bot_token,
            "minio_secret_key": self._settings.minio_secret_key,
            "database_url": self._settings.database_url,
            "qdrant_api_key": self._settings.qdrant_api_key,
        }
        value = mapping.get(name, default)
        return value if value not in (None, "") else default

    def redact(self, text: str) -> str:
        redacted = text
        for pattern in _SECRET_PATTERNS:
            if pattern.groups == 0:
                redacted = pattern.sub("***", redacted)
            else:
                redacted = pattern.sub(lambda m: f"{m.group(1)}***", redacted)
        known = [
            self._settings.app_secret_key,
            self._settings.openrouter_api_key,
            self._settings.telegram_bot_token,
            self._settings.minio_secret_key,
            self._settings.qdrant_api_key or "",
        ]
        for secret in known:
            if secret and secret not in {"change-me", ""} and secret in redacted:
                redacted = redacted.replace(secret, "***")
        return redacted

    def redact_mapping(self, data: dict[str, Any]) -> dict[str, Any]:
        secret_keys = {
            "token",
            "password",
            "secret",
            "api_key",
            "apikey",
            "authorization",
            "access_key",
        }
        result: dict[str, Any] = {}
        for key, value in data.items():
            if key.lower() in secret_keys and isinstance(value, str):
                result[key] = "***"
            elif isinstance(value, str):
                result[key] = self.redact(value)
            elif isinstance(value, dict):
                result[key] = self.redact_mapping(value)
            else:
                result[key] = value
        return result
