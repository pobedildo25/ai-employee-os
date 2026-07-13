"""Tests for OpenRouter Sonar research provider."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from app.core.config import Settings
from app.core.feature_guards import OptionalStackMisconfigured, validate_optional_stacks
from app.research.factory import create_research_manager, create_research_provider
from app.research.models import ResearchRequest
from app.research.providers.mock_provider import MockProvider
from app.research.providers.search_provider import SearchProvider
from app.research.providers.sonar_provider import SonarResearchProvider
from app.skills.registry import create_capability_registry


def _sonar_settings(**overrides) -> Settings:
    base = {
        "research_enabled": True,
        "research_provider": "sonar",
        "research_sonar_model": "perplexity/sonar",
        "openrouter_api_key": "sk-or-v1-test-key-not-real-but-long-enough",
        "openrouter_base_url": "https://openrouter.ai/api/v1",
        "skills_enabled": True,
    }
    base.update(overrides)
    return Settings(**base)


def test_validate_allows_sonar_with_openrouter_key() -> None:
    validate_optional_stacks(_sonar_settings())


def test_validate_rejects_sonar_without_key() -> None:
    with pytest.raises(OptionalStackMisconfigured, match="sonar"):
        validate_optional_stacks(
            Settings(
                research_enabled=True,
                research_provider="sonar",
                openrouter_api_key="change-me",
            )
        )


def test_create_provider_sonar() -> None:
    provider = create_research_provider(_sonar_settings())
    assert isinstance(provider, SonarResearchProvider)
    assert provider.name == "sonar"


def test_create_provider_mock_via_allow() -> None:
    provider = create_research_provider(
        Settings(research_allow_mock=True, research_provider="mock")
    )
    assert isinstance(provider, SearchProvider)
    assert isinstance(provider._backend, MockProvider)


def test_registry_registers_research_with_sonar() -> None:
    registry = create_capability_registry(_sonar_settings())
    assert registry.get_skill("research_skill") is not None
    assert "research" in {c.name for c in registry.list_available()}


@respx.mock
@pytest.mark.asyncio
async def test_sonar_provider_maps_citations_and_search_results() -> None:
    settings = _sonar_settings()
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "perplexity/sonar",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "AI marketing demand is rising.[1]",
                        }
                    }
                ],
                "citations": ["https://example.com/report"],
                "search_results": [
                    {
                        "title": "AI Marketing Report 2026",
                        "url": "https://example.com/report",
                        "snippet": "Demand up 40% YoY.",
                        "date": "2026-01-10",
                    }
                ],
            },
        )
    )
    provider = SonarResearchProvider(settings)
    hits = await provider.search(["AI marketing tools"], limit=5)
    assert route.called
    assert hits
    assert hits[0]["source_type"] == "sonar_answer"
    assert any(h.get("url") == "https://example.com/report" for h in hits)
    source = await provider.extract(hits[0])
    assert "rising" in source.extracted_content.lower() or "AI" in source.title


@respx.mock
@pytest.mark.asyncio
async def test_sonar_manager_not_marked_mock() -> None:
    settings = _sonar_settings()
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "perplexity/sonar",
                "choices": [{"message": {"role": "assistant", "content": "Brief findings."}}],
                "citations": ["https://news.example.com/a"],
                "search_results": [],
            },
        )
    )
    # interpret LLM also hits openrouter via gateway — return structured JSON second time
    # Gateway may call default model; mock any chat completion.
    manager = create_research_manager(settings)
    assert manager._is_mock_backend() is False

    # Patch researcher gateway to avoid second real-shaped call complexity:
    from unittest.mock import AsyncMock

    from app.llm.models import LLMResponse, TokenUsage

    manager._researcher._gateway.complete = AsyncMock(  # type: ignore[method-assign]
        return_value=LLMResponse(
            content=json.dumps(
                {
                    "summary": "Market growing",
                    "findings": [{"title": "F", "description": "D", "confidence": 0.8}],
                    "insights": [],
                    "recommendations": ["Feed into strategy"],
                    "confidence": 0.8,
                }
            ),
            model="mock",
            usage=TokenUsage(),
            latency_ms=1.0,
        )
    )
    result = await manager.run(ResearchRequest(query="AI marketing tools"))
    assert result.metadata.get("provider") == "sonar"
    assert result.metadata.get("strategy_ready") is True
    assert result.metadata.get("status") == "ready"
    assert result.sources
