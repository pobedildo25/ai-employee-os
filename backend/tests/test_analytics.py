import json
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.analytics.analyzer import AnalyticsAnalyzer, parse_analytics_interpretation
from app.analytics.manager import AnalyticsManager
from app.analytics.metrics import compute_all_metrics
from app.analytics.metrics.client_metrics import compute_client_metrics
from app.analytics.models import (
    AnalyticsDataset,
    AnalyticsInsight,
    AnalyticsRequest,
    AnalyticsResult,
    AnalyticsType,
)
from app.analytics.providers.data_provider import CompositeAnalyticsDataProvider
from app.analytics.validators.analytics_validator import AnalyticsValidator, result_to_document_ast
from app.api.deps import get_analytics_manager, get_client_service
from app.core.config import Settings
from app.document_intelligence.ast.models import ASTNodeType
from app.document_renderer.models import OutputFormat, RenderRequest
from app.document_renderer.renderer import DocumentRendererService
from app.main import create_app
from app.memory.models import MemoryType
from app.schemas.client import ClientRead
from app.skills.builtin.analytics_skill import AnalyticsSkill
from app.skills.registry import create_capability_registry
from tests.llm_fixtures import mock_gateway


@pytest.fixture
def settings() -> Settings:
    return Settings(skills_enabled=True)


@pytest.fixture
def client_id():
    return uuid4()


def _sample_dataset(client_id) -> AnalyticsDataset:
    return AnalyticsDataset(
        clients=[{"id": str(client_id), "name": "Acme"}],
        projects=[{"id": str(uuid4()), "name": "P1", "status": "active"}],
        tasks=[
            {"id": str(uuid4()), "status": "completed"},
            {"id": str(uuid4()), "status": "open"},
        ],
        artifacts=[{"id": str(uuid4()), "artifact_type": "document", "status": "completed", "name": "Report"}],
        executions=[
            {"status": "completed", "duration_ms": 1200},
            {"status": "failed", "duration_ms": 800},
        ],
        quality_results=[
            {"status": "PASS", "passed": True},
            {"status": "PASS", "passed": True},
            {"status": "REVISE", "needs_revision": True},
        ],
        revisions=[{"id": "r1"}],
        client_intelligence={
            "summary": "B2B SaaS client",
            "confidence": 0.8,
            "risks": ["Requires approval before publication"],
        },
        learning_rules=[{"value": "Клиент любит отчёты без таблиц"}],
        sources_used=["context", "client_intelligence", "learning"],
    )


def test_models_validation(client_id) -> None:
    request = AnalyticsRequest(
        analytics_type=AnalyticsType.CLIENT_PERFORMANCE,
        client_id=client_id,
    )
    assert request.analytics_type == AnalyticsType.CLIENT_PERFORMANCE
    insight = AnalyticsInsight(
        category="quality",
        title="Pass rate",
        description="Documents usually pass quality review",
        importance=0.7,
        confidence=0.8,
    )
    result = AnalyticsResult(
        summary="Overview",
        metrics={"client": {"projects_count": 1}},
        insights=[insight],
        recommendations=["Keep current workflow"],
        confidence=0.8,
    )
    assert result.insights[0].title == "Pass rate"


def test_metrics_calculation(client_id) -> None:
    dataset = _sample_dataset(client_id)
    client = compute_client_metrics(dataset)
    assert client["projects_count"] == 1
    assert client["artifacts_count"] == 1
    assert client["completed_tasks"] == 1
    assert client["revisions_count"] == 1
    all_metrics = compute_all_metrics(dataset)
    assert all_metrics["quality"]["pass_rate"] > 0
    assert all_metrics["execution"]["failures"] == 1


@pytest.mark.asyncio
async def test_provider_mocks(client_id) -> None:
    provider = CompositeAnalyticsDataProvider()
    dataset = await provider.collect(
        AnalyticsRequest(
            analytics_type=AnalyticsType.PROJECT_ANALYSIS,
            client_id=client_id,
            context={
                "projects": [{"id": "1", "name": "X"}],
                "tasks": [{"status": "completed"}],
                "executions": [{"status": "completed", "duration_ms": 10}],
            },
        )
    )
    assert dataset.projects
    assert "context" in dataset.sources_used


@pytest.mark.asyncio
async def test_llm_analyzer_mock(settings: Settings, client_id) -> None:
    gateway, provider = mock_gateway(
        settings,
        json.dumps(
            {
                "summary": "Documents usually pass quality review",
                "insights": [
                    {
                        "category": "quality",
                        "title": "Healthy quality",
                        "description": "Documents usually pass quality review",
                        "importance": 0.7,
                        "confidence": 0.85,
                    }
                ],
                "recommendations": ["Keep current workflow"],
                "confidence": 0.85,
            }
        ),
    )
    analyzer = AnalyticsAnalyzer(gateway)
    dataset = _sample_dataset(client_id)
    metrics = compute_all_metrics(dataset)
    heuristic = analyzer.analyze_heuristics(dataset, metrics)
    interpreted = await analyzer.interpret(
        request=AnalyticsRequest(analytics_type=AnalyticsType.CLIENT_PERFORMANCE, client_id=client_id),
        metrics=metrics,
        dataset=dataset,
        heuristic_insights=heuristic,
    )
    assert "Keep current workflow" in interpreted["recommendations"]
    assert "learning_rules" in provider.calls[0].messages[-1].content
    parsed = parse_analytics_interpretation(
        json.dumps({"summary": "ok", "insights": [], "recommendations": ["x"], "confidence": 0.5})
    )
    assert parsed["summary"] == "ok"


def test_ast_conversion(client_id) -> None:
    result = AnalyticsResult(
        analytics_type=AnalyticsType.CLIENT_PERFORMANCE,
        summary="Client performance overview",
        metrics=compute_all_metrics(_sample_dataset(client_id)),
        insights=[
            AnalyticsInsight(
                category="quality",
                title="Healthy quality",
                description="Documents usually pass quality review",
            )
        ],
        recommendations=["Keep current workflow"],
        confidence=0.8,
    )
    document_ast = result_to_document_ast(result)
    assert document_ast.root.node_type == ASTNodeType.DOCUMENT
    titles = [child.content for child in document_ast.root.children]
    assert titles == ["Executive Summary", "Metrics", "Insights", "Recommendations", "Next Steps"]
    rendered = DocumentRendererService().render(
        RenderRequest(
            document_structure=document_ast,
            output_format=OutputFormat.DOCX,
            metadata={"document_type": "docx", "kind": "analytics"},
        )
    )
    assert rendered.file_bytes is not None


@pytest.mark.asyncio
async def test_skill_registry_and_execute(settings: Settings, client_id) -> None:
    registry = create_capability_registry()
    assert registry.get_skill_for_capability("analytics") is not None

    gateway, _ = mock_gateway(
        settings,
        json.dumps(
            {
                "summary": "Analytics ready",
                "insights": [
                    {
                        "category": "client",
                        "title": "Portfolio",
                        "description": "Stable delivery",
                        "importance": 0.6,
                        "confidence": 0.8,
                    }
                ],
                "recommendations": ["Keep current workflow"],
                "confidence": 0.8,
            }
        ),
    )
    manager = AnalyticsManager(analyzer=AnalyticsAnalyzer(gateway))
    skill = AnalyticsSkill(manager=manager)
    out = await skill.execute(
        {
            "type": "CLIENT_PERFORMANCE",
            "client_id": str(client_id),
            "context": {
                "projects": [{"id": "1", "name": "P1", "status": "active"}],
                "artifacts": [{"artifact_type": "document", "status": "completed"}],
                "quality_results": [{"status": "PASS", "passed": True}],
                "client_intelligence_context": {"summary": "Known client", "confidence": 0.7},
                "learning_context": [{"value": "Клиент любит отчёты без таблиц"}],
            },
        }
    )
    assert out["status"] == "completed"
    assert out["metrics"]
    assert out["insights"]
    assert out["document_ast"]["root"]["attributes"]["kind"] == "analytics"
    assert out["memory_candidates"]
    assert out["memory_candidates"][0]["type"] == MemoryType.DECISION.value
    assert any("без таблиц" in r or "without tables" in r.lower() for r in out["recommendations"])


def test_quality_checks(client_id) -> None:
    good = AnalyticsResult(
        summary="ok",
        metrics={"client": {"projects_count": 1}},
        insights=[AnalyticsInsight(category="x", title="t", description="d")],
        recommendations=["r"],
        confidence=0.7,
    )
    assert AnalyticsValidator().validate_result(good) == []
    bad = AnalyticsResult(summary="", metrics={}, insights=[], recommendations=[], confidence=0.5)
    issues = AnalyticsValidator().quality_issues(bad)
    assert any("metrics" in i.description for i in issues)
    assert any("insights" in i.description for i in issues)


@pytest.mark.asyncio
async def test_integration_manager(settings: Settings, client_id) -> None:
    gateway, _ = mock_gateway(
        settings,
        json.dumps(
            {
                "summary": "Documents usually pass quality review",
                "insights": [],
                "recommendations": ["Keep current workflow"],
                "confidence": 0.82,
            }
        ),
    )
    manager = AnalyticsManager(analyzer=AnalyticsAnalyzer(gateway))
    result = await manager.run(
        AnalyticsRequest(
            analytics_type=AnalyticsType.CLIENT_PERFORMANCE,
            client_id=client_id,
            context=_sample_dataset(client_id).model_dump(mode="json"),
            learning_rules=[{"value": "Клиент любит отчёты без таблиц"}],
        )
    )
    assert result.document_ast is not None
    assert result.confidence > 0
    assert result.metrics["client"]["projects_count"] == 1


class FakeClientService:
    def __init__(self, client_id) -> None:
        self.client_id = client_id

    async def get_by_id(self, client_id):
        if client_id != self.client_id:
            return None
        return ClientRead.model_construct(
            id=client_id,
            name="Acme",
            description="B2B",
            created_at=None,
            updated_at=None,
        )


@pytest.mark.asyncio
async def test_api_analytics(settings: Settings, client_id) -> None:
    gateway, _ = mock_gateway(
        settings,
        json.dumps(
            {
                "summary": "Client analytics",
                "insights": [
                    {
                        "category": "client",
                        "title": "Stable",
                        "description": "ok",
                        "importance": 0.5,
                        "confidence": 0.7,
                    }
                ],
                "recommendations": ["Keep current workflow"],
                "confidence": 0.7,
            }
        ),
    )
    manager = AnalyticsManager(analyzer=AnalyticsAnalyzer(gateway))
    app = create_app()
    app.dependency_overrides[get_analytics_manager] = lambda: manager
    app.dependency_overrides[get_client_service] = lambda: FakeClientService(client_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_resp = await client.post(
            "/api/v1/analytics/run",
            json={
                "type": "CLIENT_PERFORMANCE",
                "client_id": str(client_id),
                "context": {
                    "projects": [{"id": "1", "name": "P1"}],
                    "quality_results": [{"status": "PASS", "passed": True}],
                },
            },
        )
        assert run_resp.status_code == 200
        body = run_resp.json()
        assert "summary" in body
        assert "metrics" in body
        assert isinstance(body["insights"], list)

        get_resp = await client.get(f"/api/v1/analytics/client/{client_id}")
        assert get_resp.status_code == 200
        assert "metrics" in get_resp.json()
