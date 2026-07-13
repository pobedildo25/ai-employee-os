"""Build research provider / manager from Settings (Sonar via OpenRouter or mock)."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.feature_guards import OptionalStackMisconfigured, validate_optional_stacks
from app.llm.gateway import LLMGateway, create_llm_gateway
from app.research.interfaces.researcher import ResearchProvider
from app.research.manager import ResearchManager
from app.research.providers.mock_provider import MockProvider
from app.research.providers.search_provider import SearchProvider
from app.research.providers.sonar_provider import SonarResearchProvider
from app.research.researcher import Researcher


def normalized_research_provider(settings: Settings) -> str:
    return (settings.research_provider or "none").strip().lower()


def create_research_provider(settings: Settings | None = None) -> ResearchProvider:
    """Return the configured research backend.

    - ``sonar`` — Perplexity Sonar through OpenRouter (real web grounding)
    - ``mock`` — deterministic fixtures (tests / research_allow_mock)
    """
    settings = settings or get_settings()
    name = normalized_research_provider(settings)

    if name == "sonar":
        return SonarResearchProvider(settings)

    if name == "mock" or settings.research_allow_mock:
        return SearchProvider(MockProvider())

    raise OptionalStackMisconfigured(
        f"research_provider={name!r} is not a real backend. "
        "Set RESEARCH_PROVIDER=sonar (OpenRouter) or research_allow_mock=True for tests."
    )


def create_research_manager(
    settings: Settings | None = None,
    *,
    llm_gateway: LLMGateway | None = None,
) -> ResearchManager:
    settings = settings or get_settings()
    validate_optional_stacks(settings)
    gateway = llm_gateway or create_llm_gateway(settings)
    provider = create_research_provider(settings)
    return ResearchManager(
        researcher=Researcher(provider, llm_gateway=gateway),
        llm_gateway=gateway,
    )
