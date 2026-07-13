from uuid import uuid4

import pytest

from app.agent_runtime.state.models import create_initial_state
from app.context.builder import create_context_builder
from app.core.config import Settings
from app.document_intelligence.models import AnalysisStatus, DocumentElement, DocumentRepresentation
from app.knowledge.extractor import KnowledgeExtractor
from app.knowledge.manager import KnowledgeManager
from app.knowledge.migration import KnowledgeMigrationService
from app.knowledge.models import KnowledgeItem
from app.knowledge.nodes.knowledge_migration_node import KnowledgeMigrationNode
from app.knowledge.stores.memory_store import InMemoryKnowledgeStore
from app.skills.builtin.knowledge_migration_skill import KnowledgeMigrationSkill
from app.skills.registry import create_capability_registry
from tests.llm_fixtures import knowledge_json, mock_gateway


@pytest.fixture
def settings() -> Settings:
    return Settings(skills_enabled=True)


@pytest.fixture
def client_id():
    return uuid4()


@pytest.fixture
def artifact_id():
    return uuid4()


@pytest.fixture
def representation(artifact_id) -> DocumentRepresentation:
    return DocumentRepresentation(
        artifact_id=artifact_id,
        title="Client Profile",
        document_type="docx",
        elements=[
            DocumentElement(element_type="paragraph", content="We prefer formal concise tone."),
            DocumentElement(element_type="paragraph", content="Core service is digital marketing."),
        ],
        analysis_status=AnalysisStatus.COMPLETED,
        extracted_content={"text": "We prefer formal concise tone. Core service is digital marketing."},
    )


@pytest.mark.asyncio
async def test_knowledge_extractor(settings: Settings, representation: DocumentRepresentation) -> None:
    gateway, _ = mock_gateway(settings, knowledge_json())
    extractor = KnowledgeExtractor(gateway)

    items = await extractor.extract(representation=representation, context={"goal": "migrate archive"})

    assert len(items) == 2
    assert items[0].title == "Client tone"
    assert items[0].category == "preference"
    assert items[0].confidence == 0.8
    assert items[0].source_artifact_id == representation.artifact_id


@pytest.mark.asyncio
async def test_knowledge_manager_store_search(client_id) -> None:
    manager = KnowledgeManager(InMemoryKnowledgeStore())
    item = KnowledgeItem(
        client_id=client_id,
        title="Brand color",
        category="brand",
        content="Primary color is deep navy",
        confidence=0.9,
    )
    saved = await manager.add(item)
    assert saved.id == item.id

    found = await manager.search(client_id=client_id, query="navy", limit=5)
    assert len(found) == 1
    assert found[0].title == "Brand color"

    context = await manager.get_context_for_client(client_id, query="color")
    assert context[0]["content"] == "Primary color is deep navy"


@pytest.mark.asyncio
async def test_migration_service(
    settings: Settings,
    client_id,
    artifact_id,
    representation: DocumentRepresentation,
) -> None:
    gateway, _ = mock_gateway(settings, knowledge_json())
    manager = KnowledgeManager(InMemoryKnowledgeStore())
    service = KnowledgeMigrationService(KnowledgeExtractor(gateway), manager)

    result = await service.migrate(
        client_id=client_id,
        artifacts=[
            {
                "id": str(artifact_id),
                "name": "profile.docx",
                "metadata": {"document_representation": representation.model_dump(mode="json")},
            }
        ],
        persist=True,
    )

    assert result.processed_artifacts == [artifact_id]
    assert len(result.extracted_items) == 2
    assert all(item.client_id == client_id for item in result.extracted_items)
    assert all(item.source_artifact_id == artifact_id for item in result.extracted_items)
    assert len(result.memory_candidates) >= 1
    assert result.warnings == []

    stored = await manager.list_for_client(client_id)
    assert len(stored) == 2


@pytest.mark.asyncio
async def test_migration_does_not_auto_remember(
    settings: Settings,
    client_id,
    artifact_id,
    representation: DocumentRepresentation,
) -> None:
    gateway, _ = mock_gateway(settings, knowledge_json())
    manager = KnowledgeManager(InMemoryKnowledgeStore())
    service = KnowledgeMigrationService(KnowledgeExtractor(gateway), manager)

    result = await service.migrate(
        client_id=client_id,
        artifacts=[
            {
                "id": str(artifact_id),
                "metadata": {"document_representation": representation.model_dump(mode="json")},
            }
        ],
    )

    assert result.memory_candidates
    assert all(c.get("source") == "knowledge_migration" for c in result.memory_candidates)
    # P1-F: persist defaults to False — extracted items are not auto-stored.
    stored = await manager.list_for_client(client_id)
    assert stored == []


@pytest.mark.asyncio
async def test_migration_persist_requires_high_confidence_or_confirm(
    settings: Settings,
    client_id,
    artifact_id,
    representation: DocumentRepresentation,
) -> None:
    from app.knowledge.policies.migration_policy import DEFAULT_MIN_CONFIDENCE

    assert DEFAULT_MIN_CONFIDENCE >= 0.7
    gateway, _ = mock_gateway(
        settings,
        knowledge_json(
            items=[
                {
                    "title": "Weak signal",
                    "category": "fact",
                    "content": "Low confidence note",
                    "confidence": 0.45,
                }
            ]
        ),
    )
    manager = KnowledgeManager(InMemoryKnowledgeStore())
    service = KnowledgeMigrationService(KnowledgeExtractor(gateway), manager)
    artifacts = [
        {
            "id": str(artifact_id),
            "metadata": {"document_representation": representation.model_dump(mode="json")},
        }
    ]

    low = await service.migrate(client_id=client_id, artifacts=artifacts, persist=True)
    assert low.extracted_items == [] or all(
        item.confidence < DEFAULT_MIN_CONFIDENCE for item in low.extracted_items
    )
    assert await manager.list_for_client(client_id) == []

    gateway_ok, _ = mock_gateway(settings, knowledge_json())
    service_ok = KnowledgeMigrationService(KnowledgeExtractor(gateway_ok), manager)
    confirmed = await service_ok.migrate(
        client_id=client_id,
        artifacts=artifacts,
        context={"confirm_persist": True},
    )
    assert len(confirmed.extracted_items) == 2
    stored = await manager.list_for_client(client_id)
    assert len(stored) == 2



@pytest.mark.asyncio
async def test_context_builder_knowledge_integration(client_id) -> None:
    manager = KnowledgeManager(InMemoryKnowledgeStore())
    await manager.add(
        KnowledgeItem(
            client_id=client_id,
            title="Tone",
            category="preference",
            content="Prefer formal language",
            confidence=0.85,
        )
    )

    builder = create_context_builder(knowledge_manager=manager)
    context = await builder.build(user_input="Prepare proposal", client_id=client_id)

    assert len(context.knowledge_context) == 1
    assert context.knowledge_context[0]["title"] == "Tone"
    prioritized = context.to_prioritized_dict()
    assert "knowledge_context" in prioritized


@pytest.mark.asyncio
async def test_knowledge_migration_skill(
    settings: Settings,
    client_id,
    artifact_id,
    representation: DocumentRepresentation,
) -> None:
    gateway, _ = mock_gateway(settings, knowledge_json())
    manager = KnowledgeManager(InMemoryKnowledgeStore())
    skill = KnowledgeMigrationSkill(
        migration_service=KnowledgeMigrationService(KnowledgeExtractor(gateway), manager),
        manager=manager,
    )

    output = await skill.execute(
        {
            "client_id": str(client_id),
            "artifacts": [
                {
                    "id": str(artifact_id),
                    "metadata": {"document_representation": representation.model_dump(mode="json")},
                }
            ],
        }
    )

    assert output["status"] == "completed"
    assert output["skill"] == "knowledge_migration_skill"
    assert len(output["knowledge_migration_result"]["extracted_items"]) == 2
    assert output["memory_candidates"]


def test_skill_registry_knowledge_migration(settings: Settings) -> None:
    registry = create_capability_registry(settings)
    skill = registry.get_skill("knowledge_migration_skill")
    assert skill is not None
    caps = registry.find_capabilities(["knowledge_migration"])
    assert {c.name for c in caps} == {"knowledge_migration"}


@pytest.mark.asyncio
async def test_knowledge_migration_node(
    settings: Settings,
    client_id,
    artifact_id,
    representation: DocumentRepresentation,
) -> None:
    gateway, _ = mock_gateway(settings, knowledge_json())
    manager = KnowledgeManager(InMemoryKnowledgeStore())
    node = KnowledgeMigrationNode(
        KnowledgeMigrationService(KnowledgeExtractor(gateway), manager),
    )

    state = create_initial_state(
        execution_id="exec-knowledge-1",
        trace_id="trace-knowledge-1",
        user_input="Migrate client archive",
        metadata={
            "client_id": str(client_id),
            "artifacts": [
                {
                    "id": str(artifact_id),
                    "metadata": {"document_representation": representation.model_dump(mode="json")},
                }
            ],
        },
    )
    update = await node(state)

    assert update["status"] == "knowledge_migrated"
    assert update["current_step"] == "knowledge_migration"
    assert len(update["knowledge_migration_result"]["extracted_items"]) == 2


@pytest.mark.asyncio
async def test_knowledge_migration_node_skips_without_client(settings: Settings) -> None:
    gateway, _ = mock_gateway(settings, knowledge_json())
    node = KnowledgeMigrationNode(
        KnowledgeMigrationService(KnowledgeExtractor(gateway), KnowledgeManager()),
    )
    state = create_initial_state(
        execution_id="exec-knowledge-2",
        trace_id="trace-knowledge-2",
        user_input="Migrate",
        metadata={"artifacts": []},
    )
    update = await node(state)
    assert update["status"] == "knowledge_migration_skipped"
    assert update["knowledge_migration_result"] is None
