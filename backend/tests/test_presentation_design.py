from uuid import uuid4

import pytest

from app.brand_style.models import BrandProfile
from app.core.config import Settings
from app.document_intelligence.ast.models import ASTNodeType
from app.document_renderer.models import OutputFormat, RenderRequest
from app.document_renderer.renderer import DocumentRendererService
from app.memory.models import MemoryType
from app.presentation_design.analyzer import PresentationAnalyzer
from app.presentation_design.designer import PresentationDesigner
from app.presentation_design.models import ContentBlock, PresentationPlan, PresentationType, SlidePlan, SlideType
from app.presentation_design.planner import PresentationPlanner, parse_presentation_plan
from app.presentation_design.templates import select_template_hint
from app.presentation_design.validators.presentation_validator import (
    PresentationValidator,
    plan_to_document_ast,
)
from app.skills.builtin.presentation_design_skill import PresentationDesignSkill
from app.skills.registry import create_capability_registry
from tests.llm_fixtures import mock_gateway, presentation_plan_json


@pytest.fixture
def settings() -> Settings:
    return Settings(skills_enabled=True)


def _sample_plan(*, dense: bool = False) -> PresentationPlan:
    text = ("x" * 950) if dense else "Short point"
    return PresentationPlan(
        title="Demo Deck",
        goal="Win the deal",
        audience="Buyers",
        presentation_type=PresentationType.SALES,
        slides=[
            SlidePlan(
                order=0,
                slide_type=SlideType.TITLE,
                title="Title",
                purpose="Open",
                content_blocks=[ContentBlock(text="Hello")],
            ),
            SlidePlan(
                order=1,
                slide_type=SlideType.PROBLEM,
                title="Problem",
                purpose="Pain",
                content_blocks=[ContentBlock(text=text)],
            ),
            SlidePlan(
                order=2,
                slide_type=SlideType.SOLUTION,
                title="Solution",
                purpose="Fix",
                content_blocks=[ContentBlock(text="Approach")],
            ),
            SlidePlan(
                order=3,
                slide_type=SlideType.CTA,
                title="CTA",
                purpose="Ask",
                content_blocks=[ContentBlock(text="Book a call")],
            ),
        ],
    )


def test_slide_model_validation() -> None:
    plan = parse_presentation_plan(presentation_plan_json())
    assert plan.title == "Sales Deck"
    assert plan.presentation_type == PresentationType.SALES
    assert plan.slides[0].slide_type == SlideType.TITLE
    assert plan.slides[1].slide_type == SlideType.PROBLEM
    assert len(plan.slides) == 4


def test_template_selection() -> None:
    sales = select_template_hint("sales")
    pitch = select_template_hint(PresentationType.PITCH)
    assert "PROBLEM" in sales["slide_types"]
    assert "CTA" in sales["slide_types"]
    assert "TEAM" in pitch["slide_types"]


@pytest.mark.asyncio
async def test_planner_mock(settings: Settings) -> None:
    gateway, provider = mock_gateway(settings, presentation_plan_json(title="Mock Sales"))
    planner = PresentationPlanner(gateway)
    plan = await planner.plan(
        goal="Prepare a sales presentation",
        context={"client": "Acme"},
        learning_rules=[{"key": "style", "value": "minimal"}],
        presentation_type="sales",
        trace_id="trace-plan",
    )
    assert plan.title == "Mock Sales"
    assert len(plan.slides) >= 3
    assert "learning_rules" in provider.calls[0].messages[-1].content


def test_ast_generation() -> None:
    plan = _sample_plan()
    brand = BrandProfile(colors={"primary": "#112233"}, typography={"heading_font": "Arial"})
    document_ast = plan_to_document_ast(plan, brand_profile=brand.model_dump(mode="json"))
    assert document_ast.root.node_type == ASTNodeType.DOCUMENT
    assert document_ast.root.attributes["document_type"] == "pptx"
    assert document_ast.root.attributes["brand"]["colors"]["primary"] == "#112233"
    sections = [child for child in document_ast.root.children if child.node_type == ASTNodeType.SECTION]
    assert len(sections) == 4
    assert sections[0].attributes["slide_type"] == "TITLE"


def test_brand_integration_render() -> None:
    plan = _sample_plan()
    brand = BrandProfile(
        colors={"primary": "#123456"},
        typography={"body_font": "Calibri", "heading_font": "Arial"},
        layout_rules={"margin": "wide"},
    )
    document_ast = plan_to_document_ast(plan, brand_profile=brand.model_dump(mode="json"))
    render_result = DocumentRendererService().render(
        RenderRequest(
            document_structure=document_ast,
            brand_profile=brand,
            output_format=OutputFormat.PPTX,
            metadata={"document_type": "pptx"},
        )
    )
    assert render_result.file_bytes is not None
    assert render_result.status.value == "COMPLETED"


@pytest.mark.asyncio
async def test_learning_integration(settings: Settings) -> None:
    gateway, provider = mock_gateway(settings, presentation_plan_json())
    designer = PresentationDesigner(PresentationPlanner(gateway))
    result = await designer.design(
        goal="Sales presentation",
        context={"learning_context": [{"key": "density", "value": "minimal"}]},
        learning_rules=[{"key": "density", "value": "Клиент любит минималистичные презентации"}],
        brand_profile={"colors": {"primary": "#000000"}, "typography": {"heading_font": "Arial"}},
        presentation_type="sales",
    )
    assert result.document_ast is not None
    user_msg = provider.calls[0].messages[-1].content
    assert "минималистичные" in user_msg or "learning_rules" in user_msg


@pytest.mark.asyncio
async def test_presentation_design_skill(settings: Settings) -> None:
    gateway, _ = mock_gateway(settings, presentation_plan_json())
    skill = PresentationDesignSkill(
        designer=PresentationDesigner(PresentationPlanner(gateway)),
    )
    result = await skill.execute(
        {
            "goal": "Build a sales deck",
            "context": {"client": "Acme"},
            "brand_profile": {"colors": {"primary": "#111111"}, "typography": {"body_font": "Arial"}},
            "presentation_type": "sales",
            "client_id": str(uuid4()),
            "project_id": str(uuid4()),
        }
    )
    assert result["status"] == "completed"
    assert result["presentation_plan"]["presentation_type"] == "sales"
    assert result["document_ast"]["root"]["attributes"]["document_type"] == "pptx"
    assert result["memory_candidates"]
    assert result["memory_candidates"][0]["type"] == MemoryType.DECISION.value


def test_skill_registry_includes_presentation_design() -> None:
    registry = create_capability_registry()
    names = {capability.name for capability in registry.list_available()}
    assert "presentation_design" in names
    skill = registry.get_skill_for_capability("presentation_design")
    assert skill is not None
    assert skill.name() == "presentation_design_skill"


def test_analyzer_and_quality_checks() -> None:
    plan = _sample_plan()
    warnings = PresentationAnalyzer().analyze(plan)
    assert not any("CTA" in warning for warning in warnings)

    dense = _sample_plan(dense=True)
    dense_warnings = PresentationAnalyzer().analyze(dense)
    assert any("text density" in warning.lower() or "high text" in warning.lower() for warning in dense_warnings)

    issues = PresentationValidator().quality_issues(
        plan=plan,
        document_ast=plan_to_document_ast(plan),
        brand_profile={"colors": {"primary": "#abc"}, "typography": {"heading_font": "Arial"}},
    )
    assert all(issue.category in {"structure", "content", "style"} for issue in issues) or issues == []

    weak_brand_issues = PresentationValidator().quality_issues(
        plan=plan,
        brand_profile={},
    )
    assert any("brand_style" in issue.description for issue in weak_brand_issues)
