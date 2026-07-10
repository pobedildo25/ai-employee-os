import pytest

from app.core.config import Settings
from app.quality.checks.content_check import ContentCheck
from app.quality.checks.structure_check import StructureCheck
from app.quality.checks.style_check import StyleCheck
from app.quality.gate import QualityGate
from app.quality.models import IssueSeverity, QualityIssue, ReviewStatus
from app.quality.parsers.review_parser import parse_review_response
from app.quality.reviewer import ReviewerAgent
from app.skills.builtin.quality_review_skill import QualityReviewSkill
from app.skills.registry import create_capability_registry
from tests.llm_fixtures import creation_ast_json, mock_gateway, review_json


@pytest.fixture
def settings() -> Settings:
    return Settings(skills_enabled=True)


def test_review_result_validation() -> None:
    result = parse_review_response(review_json(status="PASS", score=0.92))
    assert result.status == ReviewStatus.PASS
    assert result.score == 0.92
    assert result.summary


@pytest.mark.asyncio
async def test_reviewer_mock_pass(settings: Settings) -> None:
    gateway, _ = mock_gateway(settings, review_json(status="PASS", score=0.88))
    reviewer = ReviewerAgent(gateway)
    gate = QualityGate(reviewer)

    result, revision = await gate.evaluate(
        {
            "user_goal": "Подготовь документ",
            "decision": {"action": "EXECUTE"},
            "understanding": {"goal": "Подготовь документ"},
            "document_ast": {
                "root": {
                    "node_type": "document",
                    "children": [
                        {
                            "node_type": "section",
                            "children": [{"node_type": "heading", "content": "A", "children": []}],
                        }
                    ],
                },
                "node_count": 3,
            },
            "render_result": {"metadata": {"format": "docx"}, "status": "COMPLETED"},
        }
    )

    assert result.status == ReviewStatus.PASS
    assert revision is None


@pytest.mark.asyncio
async def test_quality_gate_pass_case(settings: Settings) -> None:
    gateway, _ = mock_gateway(settings, review_json(status="PASS", score=0.9))
    gate = QualityGate(ReviewerAgent(gateway))

    from app.document_creation.parsers.creation_parser import parse_creation_response

    document_ast, _, _, _ = parse_creation_response(creation_ast_json())
    result, revision = await gate.evaluate(
        {
            "user_goal": "Подготовь документ для клиента",
            "decision": {"action": "EXECUTE"},
            "understanding": {"goal": "Подготовь документ для клиента"},
            "document_ast": document_ast.model_dump(mode="json") if document_ast else None,
            "render_result": {"metadata": {"format": "docx"}, "status": "COMPLETED"},
            "brand_profile": {"typography": {"body_font": "Calibri"}, "colors": {"primary": "#123456"}},
        }
    )

    assert result.status == ReviewStatus.PASS
    assert result.score >= 0.7
    assert revision is None


@pytest.mark.asyncio
async def test_quality_gate_revise_case(settings: Settings) -> None:
    gateway, _ = mock_gateway(
        settings,
        review_json(
            status="REVISE",
            score=0.55,
            summary="Needs improvement",
            issues=[{"category": "content", "description": "Incomplete sections", "severity": "major"}],
            recommendations=["Add more detail to services section"],
        ),
    )
    gate = QualityGate(ReviewerAgent(gateway))
    result, revision = await gate.evaluate(
        {
            "user_goal": "Подготовь документ",
            "decision": {"action": "EXECUTE"},
            "understanding": {"goal": "Подготовь документ"},
            "document_ast": {"root": {"node_type": "document", "children": []}, "node_count": 1},
            "render_result": {"artifact_id": "00000000-0000-0000-0000-000000000001", "metadata": {"format": "docx"}},
        }
    )

    assert result.status == ReviewStatus.REVISE
    assert revision is not None
    assert revision.suggested_changes


@pytest.mark.asyncio
async def test_quality_gate_escalate_case(settings: Settings) -> None:
    gateway, _ = mock_gateway(
        settings,
        review_json(
            status="ESCALATE",
            score=0.2,
            summary="Critical issues require human review",
            issues=[{"category": "content", "description": "Missing client data", "severity": "critical"}],
        ),
    )
    gate = QualityGate(ReviewerAgent(gateway))
    result, revision = await gate.evaluate(
        {
            "user_goal": "Подготовь документ",
            "decision": {"action": "EXECUTE"},
            "understanding": {"goal": "Подготовь документ"},
            "render_result": None,
        }
    )

    assert result.status == ReviewStatus.ESCALATE
    assert revision is None


def test_content_check_missing_output() -> None:
    issues = ContentCheck().run(user_goal="Create document", context={"decision": {"action": "EXECUTE"}})
    assert any(issue.category == "content" for issue in issues)


def test_structure_check_invalid_ast() -> None:
    issues = StructureCheck().run(document_ast={"root": {"node_type": "paragraph", "children": []}, "node_count": 1})
    assert any(issue.severity == IssueSeverity.CRITICAL for issue in issues)


def test_style_check_without_brand_profile() -> None:
    issues = StyleCheck().run(brand_profile=None, render_result={"metadata": {"format": "docx"}})
    assert any(issue.category == "style" for issue in issues)


@pytest.mark.asyncio
async def test_quality_review_skill(settings: Settings) -> None:
    gateway, _ = mock_gateway(settings, review_json())
    skill = QualityReviewSkill(gate=QualityGate(ReviewerAgent(gateway)))
    result = await skill.execute(
        {
            "user_goal": "Подготовь документ",
            "decision": {"action": "EXECUTE"},
            "document_ast": {"root": {"node_type": "document", "children": [{"node_type": "section", "children": [{"node_type": "heading", "content": "Title", "children": []}]}]}, "node_count": 3},
            "render_result": {"metadata": {"format": "docx"}},
        }
    )

    assert result["status"] == "completed"
    assert result["review_result"]["status"] == ReviewStatus.PASS.value


def test_skill_registry_includes_quality_review() -> None:
    registry = create_capability_registry()
    names = {capability.name for capability in registry.list_available()}
    assert "quality_review" in names
    skill = registry.get_skill_for_capability("quality_review")
    assert skill is not None
    assert skill.name() == "quality_review_skill"
