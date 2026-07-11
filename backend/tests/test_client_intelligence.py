import json
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_client_intelligence_manager, get_client_service
from app.client_intelligence.analyzer import ClientIntelligenceAnalyzer, parse_llm_intelligence
from app.client_intelligence.builder import ClientIntelligenceBuilder
from app.client_intelligence.manager import ClientIntelligenceManager
from app.client_intelligence.models import ClientIntelligenceSources, ClientProfile
from app.client_intelligence.validators.profile_validator import ProfileValidator
from app.context.builder import create_context_builder
from app.context.models import ExecutionContext
from app.context.priority import CONTEXT_PRIORITY, build_prioritized_context
from app.core.config import Settings
from app.main import create_app
from app.memory.models import MemoryType
from app.schemas.client import ClientRead
from app.skills.builtin.client_intelligence_skill import ClientIntelligenceSkill
from app.skills.registry import create_capability_registry
from app.workspace.manager import WorkspaceManager
from app.workspace.repositories.workspace_repository import InMemoryWorkspaceRepository
from app.workspace.service import WorkspaceService
from tests.llm_fixtures import mock_gateway


@pytest.fixture
def settings() -> Settings:
    return Settings(skills_enabled=True)


@pytest.fixture
def client_id():
    return uuid4()


def test_profile_models(client_id) -> None:
    profile = ClientProfile(
        client_id=client_id,
        summary="Компания из B2B SaaS сегмента",
        preferences={"document_style": "minimal", "language": "formal"},
        communication_style={"tone": "professional", "verbosity": "short"},
        risks=["Requires approval before publication"],
        confidence=0.85,
        sources_used=["memory", "learning"],
    )
    assert profile.preferences["document_style"] == "minimal"
    assert profile.communication_style["verbosity"] == "short"


def test_analyzer_heuristics(client_id) -> None:
    sources = ClientIntelligenceSources(
        client_id=client_id,
        memory_items=[
            {
                "type": "PREFERENCE",
                "content": "Клиент всегда просит короткие презентации",
                "importance": 0.8,
            }
        ],
        learning_rules=[{"key": "language", "value": "formal", "confidence": 0.9}],
        notes=["Requires approval before publication"],
    )
    signals = ClientIntelligenceAnalyzer().analyze_heuristics(sources)
    keys = {(s.category, s.key, s.value) for s in signals}
    assert any(item[0] == "preference" and item[2] == "short" for item in keys)
    assert any(item[0] == "risk" for item in keys)


def test_llm_analyzer_parse() -> None:
    raw = json.dumps(
        {
            "summary": "B2B SaaS",
            "signals": [
                {
                    "category": "preference",
                    "key": "presentation_length",
                    "value": "short",
                    "confidence": 0.9,
                }
            ],
            "recommendations": ["Keep decks short"],
            "confidence": 0.88,
        }
    )
    parsed = parse_llm_intelligence(raw)
    assert parsed["signals"][0].key == "presentation_length"
    assert parsed["confidence"] == 0.88


@pytest.mark.asyncio
async def test_builder_and_manager(client_id) -> None:
    manager = ClientIntelligenceManager()
    result = await manager.build_profile(
        client_id,
        execution_context={
            "client_context": {"name": "Acme", "description": "B2B SaaS"},
            "memory_context": [
                {"type": "PREFERENCE", "content": "Client prefers concise presentations", "importance": 0.9}
            ],
            "learning_context": [{"key": "verbosity", "value": "short", "confidence": 0.8}],
            "workspace_context": {"active_project_id": str(uuid4()), "active_artifact_id": str(uuid4())},
        },
        use_llm=False,
    )
    assert result.profile.summary
    assert result.profile.preferences.get("verbosity") == "short" or result.profile.preferences
    assert result.memory_candidates
    assert any(item["type"] == MemoryType.PREFERENCE.value for item in result.memory_candidates)
    assert "memory" in result.profile.sources_used or "learning" in result.profile.sources_used


@pytest.mark.asyncio
async def test_context_integration(settings: Settings, client_id) -> None:
    workspace = WorkspaceService(WorkspaceManager(InMemoryWorkspaceRepository()))
    await workspace.open(client_id=client_id)
    manager = ClientIntelligenceManager(workspace_service=workspace)
    builder = create_context_builder(
        workspace_service=workspace,
        client_intelligence_manager=manager,
    )
    context = await builder.build(user_input="Prepare report", client_id=client_id)
    assert context.client_intelligence_context is not None
    assert context.client_intelligence_context["client_id"] == str(client_id)
    prioritized = context.to_prioritized_dict()
    assert "client_intelligence_context" in prioritized
    assert list(CONTEXT_PRIORITY).index("knowledge_context") < list(CONTEXT_PRIORITY).index(
        "client_intelligence_context"
    )
    assert list(CONTEXT_PRIORITY).index("client_intelligence_context") < list(CONTEXT_PRIORITY).index(
        "learning_context"
    )


@pytest.mark.asyncio
async def test_skill_registry_and_execute(settings: Settings, client_id) -> None:
    registry = create_capability_registry()
    assert registry.get_skill_for_capability("client_intelligence") is not None

    gateway, _ = mock_gateway(
        settings,
        json.dumps(
            {
                "summary": "B2B SaaS company",
                "signals": [
                    {
                        "category": "preference",
                        "key": "presentation_length",
                        "value": "short",
                        "confidence": 0.9,
                    }
                ],
                "recommendations": ["Use short decks"],
                "risks": ["Requires approval before publication"],
                "confidence": 0.9,
            }
        ),
    )
    analyzer = ClientIntelligenceAnalyzer(gateway)
    manager = ClientIntelligenceManager(
        analyzer=analyzer,
        builder=ClientIntelligenceBuilder(analyzer),
    )
    skill = ClientIntelligenceSkill(manager=manager)
    out = await skill.execute(
        {
            "client_id": str(client_id),
            "context": {
                "memory_context": [
                    {"type": "FACT", "content": "Клиент всегда просит короткие презентации"}
                ]
            },
            "use_llm": True,
        }
    )
    assert out["status"] == "completed"
    assert out["profile"]["confidence"] >= 0.0
    assert out["memory_candidates"]


def test_quality_checks(client_id) -> None:
    profile = ClientProfile(
        client_id=client_id,
        summary="Known client",
        preferences={"language": "formal"},
        communication_style={"tone": "professional"},
        risks=["approval"],
        recommendations=["Keep formal tone"],
        confidence=0.8,
        sources_used=["memory"],
    )
    assert ProfileValidator().validate(profile) == []
    weak = ClientProfile(client_id=client_id, summary="", confidence=0.1)
    warnings = ProfileValidator().validate(weak)
    assert warnings
    issues = ProfileValidator().quality_issues(weak)
    assert issues


@pytest.mark.asyncio
async def test_workspace_integration(client_id) -> None:
    workspace = WorkspaceService(WorkspaceManager(InMemoryWorkspaceRepository()))
    snapshot = await workspace.open(client_id=client_id)
    manager = ClientIntelligenceManager(workspace_service=workspace)
    sources = await manager.collect_sources(client_id)
    assert sources.workspace.get("workspace_id") == snapshot["workspace_id"]
    assert sources.workspace.get("client_id") == str(client_id)


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
async def test_api_intelligence(client_id) -> None:
    manager = ClientIntelligenceManager()
    app = create_app()
    app.dependency_overrides[get_client_service] = lambda: FakeClientService(client_id)
    app.dependency_overrides[get_client_intelligence_manager] = lambda: manager

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        get_resp = await client.get(f"/api/v1/clients/{client_id}/intelligence")
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert "profile" in body
        assert "confidence" in body

        post_resp = await client.post(
            f"/api/v1/clients/{client_id}/intelligence/analyze",
            json={
                "use_llm": False,
                "context": {
                    "memory_context": [
                        {"type": "PREFERENCE", "content": "formal communication", "importance": 0.8}
                    ]
                },
            },
        )
        assert post_resp.status_code == 200
        analyzed = post_resp.json()
        assert analyzed["profile"]["client_id"] == str(client_id)
