"""Fail-closed guards for optional stacks that still lack real providers."""

from __future__ import annotations

from app.core.config import Settings


class OptionalStackMisconfigured(RuntimeError):
    """Raised when research/semantic flags are on without a safe backend."""


def _openrouter_configured(settings: Settings) -> bool:
    key = (settings.openrouter_api_key or "").strip()
    return bool(key) and key != "change-me"


def research_backend_ready(settings: Settings) -> bool:
    """True when research may be enabled without falling back to silent Mock."""
    if settings.research_allow_mock:
        return True
    provider = (settings.research_provider or "none").strip().lower()
    if provider == "sonar" and _openrouter_configured(settings):
        return True
    if provider == "mock" and settings.research_allow_mock:
        return True
    return False


def validate_optional_stacks(settings: Settings) -> None:
    """Refuse research/semantic enable without real provider or explicit test escape hatch.

    Research: ``research_provider=sonar`` + OpenRouter key, or ``research_allow_mock`` for tests.
    Semantic: real embeddings required later; stub only with ``embedding_allow_stub``.
    """
    if settings.research_enabled and not research_backend_ready(settings):
        raise OptionalStackMisconfigured(
            "research_enabled=True requires RESEARCH_PROVIDER=sonar with a real "
            "OPENROUTER_API_KEY, or research_allow_mock=True for tests only."
        )
    if settings.semantic_memory_enabled and not settings.embedding_allow_stub:
        raise OptionalStackMisconfigured(
            "semantic_memory_enabled=True requires real embeddings; "
            "stub_embed is not allowed. Keep semantic_memory_enabled=False "
            "or set embedding_allow_stub=True only for tests."
        )
