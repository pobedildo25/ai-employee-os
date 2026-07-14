import json
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_research_manager
from app.context.builder import create_context_builder
from app.core.config import Settings
from app.document_intelligence.ast.models import ASTNodeType
from app.document_renderer.models import OutputFormat, RenderRequest
from app.document_renderer.renderer import DocumentRendererService
from app.main import create_app
from app.memory.models import MemoryType
from app.research.manager import ResearchManager
from app.research.models import ResearchRequest, ResearchSource, ResearchType
from app.research.providers.mock_provider import MockProvider
from app.research.providers.search_provider import SearchProvider
from app.research.query_builder import ResearchQueryBuilder
from app.research.researcher import Researcher, parse_research_interpretation
from app.research.source_ranker import SourceRanker
from app.research.validators.research_validator import ResearchValidator, result_to_document_ast
from app.skills.builtin.research_skill import ResearchSkill
from app.skills.registry import create_capability_registry
from tests.llm_fixtures import mock_gateway


@pytest.fixture
def settings() -> Settings:
    return Settings(skills_enabled=True)


def test_models_validation() -> None:
    request = ResearchRequest(query="AI marketing tools", research_type=ResearchType.MARKET_RESEARCH)
    assert request.query
    source = ResearchSource(
        title="Market overview",
        url="https://example.com/a",
        extracted_content="Growing demand",
        credibility_score=0.8,
    )
    assert source.credibility_score == 0.8


@pytest.mark.asyncio
async def test_provider_mocks() -> None:
    provider = MockProvider()
    hits = await provider.search(["AI marketing tools"], limit=3)
    assert len(hits) == 3
    source = await provider.extract(hits[0])
    assert source.title
    fetched = await provider.fetch(hits[0]["url"])
    assert "content" in fetched
    search = SearchProvider(provider)
    assert await search.search(["x"], limit=1)


def test_query_builder() -> None:
    queries = ResearchQueryBuilder().build(
        ResearchRequest(
            query="AI marketing tools",
            research_type=ResearchType.MARKET_RESEARCH,
            context={
                "client_intelligence_context": {
                    "summary": "B2B SaaS",
                    "industry": "SaaS",
                },
                "strategy_context": {"strategy_type": "go_to_market"},
            },
            constraints=["last 12 months"],
        )
    )
    assert queries[0] == "AI marketing tools"
    assert any("SaaS" in q for q in queries)
    assert any("go_to_market" in q for q in queries)


def test_source_ranking() -> None:
    sources = [
        ResearchSource(
            title="Old note",
            url="https://example.com/old",
            extracted_content="misc",
            credibility_score=0.4,
        ),
        ResearchSource(
            title="AI marketing tools demand",
            url="https://example.com/new",
            extracted_content="AI marketing tools growing demand",
            credibility_score=0.9,
        ),
    ]
    ranked = SourceRanker().rank(sources, query="AI marketing tools")
    assert ranked[0].title.startswith("AI marketing")


@pytest.mark.asyncio
async def test_analyzer_mock(settings: Settings) -> None:
    gateway, provider = mock_gateway(
        settings,
        json.dumps(
            {
                "summary": "Market is expanding",
                "findings": [
                    {
                        "title": "Launch",
                        "description": "Company A launched product",
                        "source_urls": ["https://example.com/1"],
                        "confidence": 0.8,
                    }
                ],
                "insights": [
                    {
                        "category": "market",
                        "title": "Market shift",
                        "description": "Demand is rising for AI marketing tools",
                        "importance": 0.8,
                        "confidence": 0.85,
                    }
                ],
                "recommendations": ["Feed research into strategy_analysis"],
                "confidence": 0.84,
            }
        ),
    )
    manager = ResearchManager(
        researcher=Researcher(SearchProvider(MockProvider()), llm_gateway=gateway),
        llm_gateway=gateway,
    )
    result = await manager.run(
        ResearchRequest(
            query="AI marketing tools",
            research_type=ResearchType.MARKET_RESEARCH,
            context={"client_intelligence_context": {"summary": "SaaS client"}},
        )
    )
    assert result.sources
    assert result.findings
    assert result.insights
    assert result.document_ast is not None
    assert "Market shift" in provider.calls[0].messages[-1].content or "insights" in provider.calls[0].messages[-1].content
    parsed = parse_research_interpretation(
        json.dumps({"summary": "ok", "findings": [], "insights": [], "recommendations": ["x"], "confidence": 0.5})
    )
    assert parsed["summary"] == "ok"


def test_ast_conversion() -> None:
    from app.research.models import ResearchFinding, ResearchInsight, ResearchResult

    result = ResearchResult(
        query="AI marketing tools",
        research_type=ResearchType.MARKET_RESEARCH,
        summary="Overview",
        sources=[ResearchSource(title="S1", url="https://example.com/1", extracted_content="Growing demand")],
        findings=[ResearchFinding(title="F1", description="Demand up")],
        insights=[ResearchInsight(category="market", title="Market shift", description="...")],
        recommendations=["Use in strategy"],
        confidence=0.8,
    )
    document_ast = result_to_document_ast(result)
    assert document_ast.root.node_type == ASTNodeType.DOCUMENT
    titles = [c.content for c in document_ast.root.children]
    assert titles == ["Executive Summary", "Sources", "Findings", "Market Insights", "Recommendations"]
    rendered = DocumentRendererService().render(
        RenderRequest(
            document_structure=document_ast,
            output_format=OutputFormat.DOCX,
            metadata={"document_type": "docx", "kind": "research"},
        )
    )
    assert rendered.file_bytes is not None


@pytest.mark.asyncio
async def test_skill_registry_and_strategy_handoff(settings: Settings) -> None:
    registry = create_capability_registry(
        Settings(skills_enabled=True, research_enabled=True, research_allow_mock=True)
    )
    assert registry.get_skill_for_capability("research") is not None
    assert registry.get_skill_for_capability("strategy_analysis") is not None

    gateway, _ = mock_gateway(
        settings,
        json.dumps(
            {
                "summary": "Ready for strategy",
                "findings": [{"title": "F", "description": "D", "confidence": 0.7}],
                "insights": [
                    {
                        "category": "market",
                        "title": "Market shift",
                        "description": "Growing segment",
                        "importance": 0.7,
                        "confidence": 0.8,
                    }
                ],
                "recommendations": ["Feed research into strategy_analysis"],
                "confidence": 0.8,
            }
        ),
    )
    manager = ResearchManager(
        researcher=Researcher(MockProvider(), llm_gateway=gateway),
        llm_gateway=gateway,
    )
    skill = ResearchSkill(manager=manager)
    out = await skill.execute(
        {
            "query": "AI marketing tools",
            "type": "MARKET_RESEARCH",
            "context": {"strategy_context": {"strategy_type": "go_to_market"}},
        }
    )
    # Mock research must never present as product success.
    assert out["status"] == "incomplete"
    assert out["memory_candidates"]
    assert out["memory_candidates"][0]["type"] == MemoryType.KNOWLEDGE.value
    assert out["metadata"].get("strategy_ready") is False
    assert out["metadata"].get("status") == "mock_not_production"
    assert out["document_ast"]["root"]["attributes"]["kind"] == "research"


def test_quality_checks() -> None:
    from app.research.models import ResearchFinding, ResearchResult

    good = ResearchResult(
        query="q",
        sources=[ResearchSource(title="s", url="https://x")],
        findings=[ResearchFinding(title="f", description="d")],
        confidence=0.7,
    )
    assert ResearchValidator().validate_result(good) == []
    bad = ResearchResult(query="q", sources=[], findings=[], confidence=0.5)
    issues = ResearchValidator().quality_issues(bad)
    assert any("sources" in i.description for i in issues)
    assert any("findings" in i.description for i in issues)


@pytest.mark.asyncio
async def test_context_provider_integration(settings: Settings) -> None:
    gateway, _ = mock_gateway(
        settings,
        json.dumps(
            {
                "summary": "Cached research",
                "findings": [{"title": "F", "description": "D", "confidence": 0.7}],
                "insights": [],
                "recommendations": ["Next: strategy"],
                "confidence": 0.7,
            }
        ),
    )
    manager = ResearchManager(
        researcher=Researcher(MockProvider(), llm_gateway=gateway),
        llm_gateway=gateway,
    )
    client_id = uuid4()
    result = await manager.run(
        ResearchRequest(query="AI marketing tools", client_id=client_id),
    )
    builder = create_context_builder(research_manager=manager)
    context = await builder.build(user_input="continue", client_id=client_id)
    assert context.research_context is not None
    assert context.research_context["id"] == str(result.id)


@pytest.mark.asyncio
async def test_api_research_disabled_by_default(settings: Settings) -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_resp = await client.post(
            "/api/v1/research/run",
            json={"type": "MARKET_RESEARCH", "query": "AI marketing tools"},
        )
        assert run_resp.status_code == 503
        assert "disabled" in run_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_api_research(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.v1.research.get_settings",
        lambda: Settings(
            research_enabled=True, skills_enabled=True, research_allow_mock=True
        ),
    )
    gateway, _ = mock_gateway(
        settings,
        json.dumps(
            {
                "summary": "API research",
                "findings": [{"title": "F", "description": "D", "confidence": 0.7}],
                "insights": [
                    {
                        "category": "market",
                        "title": "Market shift",
                        "description": "...",
                        "importance": 0.7,
                        "confidence": 0.8,
                    }
                ],
                "recommendations": ["Feed research into strategy_analysis"],
                "confidence": 0.8,
            }
        ),
    )
    manager = ResearchManager(
        researcher=Researcher(MockProvider(), llm_gateway=gateway),
        llm_gateway=gateway,
    )
    app = create_app()
    app.dependency_overrides[get_research_manager] = lambda: manager

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_resp = await client.post(
            "/api/v1/research/run",
            json={"type": "MARKET_RESEARCH", "query": "AI marketing tools"},
        )
        assert run_resp.status_code == 200
        body = run_resp.json()
        assert body["summary"]
        assert body["sources"]
        assert body["metadata"].get("strategy_ready") is False
        assert body["metadata"].get("status") == "mock_not_production"
        research_id = body["id"]

        get_resp = await client.get(f"/api/v1/research/{research_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == research_id
