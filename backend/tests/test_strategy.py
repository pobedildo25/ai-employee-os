from uuid import uuid4

import pytest

from app.core.config import Settings
from app.document_intelligence.ast.models import ASTNodeType
from app.document_renderer.models import OutputFormat, RenderRequest
from app.document_renderer.renderer import DocumentRendererService
from app.memory.models import MemoryType
from app.skills.builtin.strategy_skill import StrategySkill
from app.skills.registry import create_capability_registry
from app.strategy.analyzer import StrategyAnalyzer
from app.strategy.frameworks import normalize_framework, section_hints_for
from app.strategy.frameworks.swot import empty_swot, normalize_swot
from app.strategy.models import (
    StrategyInsight,
    StrategyRequest,
    StrategyResult,
    StrategyType,
)
from app.strategy.planner import StrategyPlanner, parse_strategy_result
from app.strategy.strategist import StrategyStrategist
from app.strategy.validators.strategy_validator import StrategyValidator, result_to_document_ast
from tests.llm_fixtures import mock_gateway, strategy_result_json


@pytest.fixture
def settings() -> Settings:
    return Settings(skills_enabled=True)


def test_models_validation() -> None:
    request = StrategyRequest(goal="Build marketing strategy", audience="SMB")
    assert request.goal
    result = parse_strategy_result(strategy_result_json())
    assert result.strategy_type == StrategyType.MARKETING_STRATEGY
    assert len(result.insights) >= 1
    assert result.recommendations


def test_framework_generation() -> None:
    swot = normalize_swot(
        {
            "strengths": ["Brand"],
            "weaknesses": ["Reach"],
            "opportunities": ["Partners"],
            "threats": ["Price wars"],
        }
    )
    assert swot["strengths"] == ["Brand"]
    assert set(empty_swot()) == {"strengths", "weaknesses", "opportunities", "threats"}

    plan = normalize_framework(
        StrategyType.MARKETING_STRATEGY,
        {"goals": ["Pipeline"], "channels": ["Content"], "content": ["Guides"], "metrics": ["MQLs"]},
    )
    assert plan["goals"] == ["Pipeline"]
    assert "Executive Summary" in section_hints_for(StrategyType.SWOT_ANALYSIS)
    assert "Differentiation" in section_hints_for("positioning")


@pytest.mark.asyncio
async def test_planner_mock(settings: Settings) -> None:
    gateway, provider = mock_gateway(settings, strategy_result_json(summary="Short ICP focus"))
    planner = StrategyPlanner(gateway)
    result = await planner.plan(
        StrategyRequest(
            goal="Сделай маркетинговую стратегию для клиента",
            client_context={"name": "Acme"},
            learning_rules=[{"key": "report_length", "value": "Клиент предпочитает короткие отчеты"}],
            strategy_type=StrategyType.MARKETING_STRATEGY,
        ),
        trace_id="trace-strategy",
    )
    assert result.summary.startswith("Short")
    assert "learning_rules" in provider.calls[0].messages[-1].content
    assert "короткие" in provider.calls[0].messages[-1].content


def test_ast_conversion() -> None:
    result = parse_strategy_result(strategy_result_json())
    document_ast = result_to_document_ast(result)
    assert document_ast.root.node_type == ASTNodeType.DOCUMENT
    assert document_ast.root.attributes["kind"] == "strategy"
    titles = [child.content for child in document_ast.root.children]
    assert "Executive Summary" in titles
    assert "Recommendations" in titles
    assert "Next Steps" in titles


def test_ast_to_renderer() -> None:
    result = parse_strategy_result(strategy_result_json())
    document_ast = result_to_document_ast(result)
    rendered = DocumentRendererService().render(
        RenderRequest(
            document_structure=document_ast,
            output_format=OutputFormat.DOCX,
            metadata={"document_type": "docx", "kind": "strategy"},
        )
    )
    assert rendered.file_bytes is not None
    assert rendered.status.value == "COMPLETED"


@pytest.mark.asyncio
async def test_learning_context(settings: Settings) -> None:
    gateway, provider = mock_gateway(settings, strategy_result_json())
    strategist = StrategyStrategist(StrategyPlanner(gateway))
    result = await strategist.analyze(
        StrategyRequest(
            goal="Marketing strategy",
            learning_rules=[{"value": "Клиент предпочитает короткие отчеты"}],
            brand_profile={"colors": {"primary": "#111"}, "typography": {"heading_font": "Arial"}},
        )
    )
    assert result.document_ast is not None
    assert result.metadata.get("brand_profile_passthrough") is True
    assert "короткие" in provider.calls[0].messages[-1].content


@pytest.mark.asyncio
async def test_strategy_skill(settings: Settings) -> None:
    gateway, _ = mock_gateway(settings, strategy_result_json())
    skill = StrategySkill(strategist=StrategyStrategist(StrategyPlanner(gateway)))
    out = await skill.execute(
        {
            "goal": "Сделай маркетинговую стратегию для клиента",
            "context": {"client": {"name": "Acme"}},
            "strategy_type": "marketing_strategy",
            "client_id": str(uuid4()),
            "project_id": str(uuid4()),
        }
    )
    assert out["status"] == "completed"
    assert out["strategy_result"]["strategy_type"] == "marketing_strategy"
    assert out["document_ast"]["root"]["attributes"]["kind"] == "strategy"
    assert out["memory_candidates"]
    assert out["memory_candidates"][0]["type"] == MemoryType.DECISION.value


def test_skill_registry_includes_strategy() -> None:
    registry = create_capability_registry()
    names = {capability.name for capability in registry.list_available()}
    assert "strategy_analysis" in names
    skill = registry.get_skill_for_capability("strategy_analysis")
    assert skill is not None
    assert skill.name() == "strategy_skill"


def test_quality_checks() -> None:
    request = StrategyRequest(goal="Build strategy")
    result = parse_strategy_result(strategy_result_json())
    document_ast = result_to_document_ast(result)
    issues = StrategyValidator().quality_issues(
        request=request,
        result=result,
        document_ast=document_ast,
    )
    assert issues == [] or all(issue.severity.value in {"minor", "major", "critical"} for issue in issues)

    empty = StrategyResult(summary="", insights=[], recommendations=[])
    bad = StrategyValidator().quality_issues(result=empty)
    assert any("recommendations" in issue.description for issue in bad)
    assert any("insights" in issue.description for issue in bad)

    warnings = StrategyAnalyzer().analyze(
        StrategyResult(
            summary="",
            insights=[],
            recommendations=[],
        )
    )
    assert warnings


@pytest.mark.asyncio
async def test_integration_strategist_ast(settings: Settings) -> None:
    gateway, _ = mock_gateway(
        settings,
        strategy_result_json(strategy_type="swot_analysis", summary="SWOT overview"),
    )
    strategist = StrategyStrategist(StrategyPlanner(gateway))
    result = await strategist.analyze(
        StrategyRequest(
            goal="SWOT for client",
            strategy_type=StrategyType.SWOT_ANALYSIS,
            client_context={"industry": "SaaS"},
        )
    )
    assert result.strategy_type == StrategyType.SWOT_ANALYSIS
    assert result.document_ast is not None
    assert isinstance(result.insights[0], StrategyInsight) or result.insights
    sections = result.document_ast["root"]["children"]
    assert len(sections) >= 3
