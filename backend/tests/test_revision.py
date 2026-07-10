from uuid import uuid4

import pytest

from app.agent_runtime.checkpoint.manager import InMemoryCheckpointManager
from app.agent_runtime.graph.edges import ROUTE_END, ROUTE_REVISE, route_after_quality
from app.agent_runtime.runtime import AgentRuntime, build_executive_graph
from app.agent_runtime.state.models import create_initial_state
from app.core.config import Settings
from app.quality.models import IssueSeverity, QualityIssue, ReviewStatus
from app.revision.agent import RevisionAgent
from app.revision.manager import RevisionManager
from app.revision.models import RevisionRequest, RevisionStatus
from app.revision.parsers.feedback_parser import build_revision_request_from_review, parse_user_feedback
from app.revision.policies.revision_policy import MAX_AUTOMATIC_REVISIONS, can_auto_revise, should_wait_for_user
from app.schemas.artifact import ArtifactUploadRequest
from app.skills.builtin.revision_skill import RevisionSkill
from app.skills.registry import create_capability_registry
from tests.llm_fixtures import (
    creation_ast_json,
    executive_json,
    mock_gateway,
    plan_json,
    review_json,
    revision_json,
)


@pytest.fixture
def settings() -> Settings:
    return Settings(skills_enabled=True)


def test_revision_request_validation() -> None:
    request = RevisionRequest(
        source_artifact_id=uuid4(),
        issues=[QualityIssue(category="content", description="Too brief", severity=IssueSeverity.MAJOR)],
        suggested_changes=["Add more detail"],
        user_feedback="Сделай больше деталей",
        revision_count=0,
    )
    assert request.revision_count == 0
    assert request.user_feedback is not None


def test_revision_policy_max_limit() -> None:
    assert MAX_AUTOMATIC_REVISIONS == 1
    assert can_auto_revise(0) is True
    assert can_auto_revise(1) is False
    assert should_wait_for_user(1) is True


def test_feedback_parsing() -> None:
    suggestions = parse_user_feedback("Сделай меньше текста")
    assert any("concise" in item.lower() or "меньше" in item.lower() for item in suggestions)

    detailed = parse_user_feedback("Добавь больше деталей")
    assert any("detail" in item.lower() or "детал" in item.lower() for item in detailed)


def test_build_revision_request_merges_feedback() -> None:
    request = build_revision_request_from_review(
        issues=[{"category": "content", "description": "Incomplete", "severity": "major"}],
        suggested_changes=["Expand services"],
        user_feedback="Сделай меньше текста",
        revision_count=0,
        source_artifact_id=uuid4(),
    )
    assert request.source_artifact_id is not None
    assert len(request.suggested_changes) >= 2


def test_route_after_quality_revise_once() -> None:
    state = create_initial_state(execution_id="e1", trace_id="t1", user_input="test")
    state["review_result"] = {"status": ReviewStatus.REVISE.value}
    state["revision_count"] = 0
    assert route_after_quality(state) == ROUTE_REVISE

    state["revision_count"] = 1
    assert route_after_quality(state) == ROUTE_END

    state["review_result"] = {"status": ReviewStatus.PASS.value}
    state["revision_count"] = 0
    assert route_after_quality(state) == ROUTE_END


@pytest.mark.asyncio
async def test_revision_agent_mock(settings: Settings) -> None:
    gateway, _ = mock_gateway(settings, revision_json())
    agent = RevisionAgent(gateway)
    request = RevisionRequest(
        issues=[QualityIssue(category="content", description="Needs improvement")],
        suggested_changes=["Improve overview"],
        revision_count=0,
    )
    result = await agent.revise(request, document_ast=None, context={})
    assert result.status == RevisionStatus.COMPLETED
    assert result.document_ast is not None
    assert result.changes_applied


@pytest.mark.asyncio
async def test_revision_waiting_user_when_limit_reached(settings: Settings) -> None:
    gateway, _ = mock_gateway(settings, revision_json())
    manager = RevisionManager(RevisionAgent(gateway))
    request = RevisionRequest(revision_count=1, suggested_changes=["More detail"])
    result = await manager.apply_revision(request, document_ast=None)
    assert result.status == RevisionStatus.WAITING_USER


@pytest.mark.asyncio
async def test_artifact_version_creation_on_revision(settings: Settings, artifact_service) -> None:
    client_id, project_id = uuid4(), uuid4()
    uploaded = await artifact_service.upload_artifact(
        ArtifactUploadRequest(
            client_id=client_id,
            project_id=project_id,
            name="generated.docx",
            artifact_type="generated_document",
            metadata={"generated_by": "document_renderer"},
        ),
        file_data=b"original-bytes",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    gateway, _ = mock_gateway(settings, revision_json(title="Revised Document"))
    manager = RevisionManager(RevisionAgent(gateway), artifact_service=artifact_service)

    from app.document_creation.parsers.creation_parser import parse_creation_response
    from tests.llm_fixtures import creation_ast_json as _creation_ast_json

    document_ast, _, _, _ = parse_creation_response(_creation_ast_json())
    request = RevisionRequest(
        source_artifact_id=uploaded.id,
        issues=[QualityIssue(category="content", description="Improve structure")],
        suggested_changes=["Refine sections"],
        revision_count=0,
    )

    result = await manager.apply_revision(
        request,
        document_ast=document_ast.model_dump(mode="json") if document_ast else None,
        client_id=client_id,
        project_id=project_id,
        output_format="docx",
    )

    assert result.status == RevisionStatus.COMPLETED
    assert result.artifact_id == uploaded.id
    assert result.version_id is not None

    history = await artifact_service.get_artifact_history(uploaded.id)
    assert len(history) >= 2


@pytest.mark.asyncio
async def test_revision_skill(settings: Settings) -> None:
    gateway, _ = mock_gateway(settings, revision_json())
    skill = RevisionSkill(manager=RevisionManager(RevisionAgent(gateway)))
    result = await skill.execute(
        {
            "revision_request": {
                "issues": [{"category": "content", "description": "Too short", "severity": "major"}],
                "suggested_changes": ["Expand"],
                "revision_count": 0,
            },
            "user_feedback": "Добавь больше деталей",
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
        }
    )
    assert result["status"] == "completed"
    assert result["revision_result"]["status"] == RevisionStatus.COMPLETED.value
    assert result["memory_candidates"]


def test_skill_registry_includes_document_revision() -> None:
    registry = create_capability_registry()
    names = {capability.name for capability in registry.list_available()}
    assert "document_revision" in names
    skill = registry.get_skill_for_capability("document_revision")
    assert skill is not None
    assert skill.name() == "revision_skill"


@pytest.mark.asyncio
async def test_langgraph_revision_loop(settings: Settings) -> None:
    registry = create_capability_registry(settings)
    gateway, _ = mock_gateway(
        settings,
        executive_json(
            goal="Подготовь документ",
            summary="Нужен документ",
            action="EXECUTE",
            required_capabilities=["document_creation", "document_rendering"],
            next_action="execute",
        ),
        plan_json(goal="Подготовь документ"),
        creation_ast_json(title="Initial Document"),
        review_json(
            status="REVISE",
            score=0.5,
            summary="Needs improvement",
            issues=[{"category": "content", "description": "Incomplete", "severity": "major"}],
            recommendations=["Add more detail"],
        ),
        revision_json(title="Improved Document"),
        review_json(status="PASS", score=0.9, summary="Looks good after revision"),
    )
    runtime = AgentRuntime(
        graph=build_executive_graph(gateway, capability_registry=registry),
        checkpoint_manager=InMemoryCheckpointManager(),
    )

    result = await runtime.execute(
        "Подготовь документ для клиента",
        metadata={"auto_approve": True},
    )

    assert result["revision_count"] == 1
    assert result["revision_result"] is not None
    assert result["revision_result"]["status"] == RevisionStatus.COMPLETED.value
    assert result["review_result"]["status"] == ReviewStatus.PASS.value
    assert result["quality_check"]["passed"] is True
