from uuid import UUID

from app.knowledge.models import KnowledgeItem, KnowledgeMigrationResult
from app.memory.models import MemoryItem, MemoryType


def prepare_knowledge_memory_items(
    result: KnowledgeMigrationResult,
    *,
    client_id: UUID | None = None,
    project_id: UUID | None = None,
    session_id: str | None = None,
) -> list[MemoryItem]:
    """Prepare memory candidates from knowledge migration without auto-saving."""
    items: list[MemoryItem] = []

    if result.extracted_items:
        items.append(
            MemoryItem(
                type=MemoryType.FACT,
                content=(
                    f"Клиентская база знаний пополнена: "
                    f"{len(result.extracted_items)} элементов из "
                    f"{len(result.processed_artifacts)} артефактов"
                ),
                metadata={
                    "kind": "knowledge_migration_fact",
                    "item_count": len(result.extracted_items),
                    "artifact_count": len(result.processed_artifacts),
                },
                importance=0.6,
                source="knowledge_migration",
                client_id=client_id,
                project_id=project_id,
                session_id=session_id,
            )
        )

    for knowledge in result.extracted_items[:5]:
        items.append(
            MemoryItem(
                type=MemoryType.KNOWLEDGE,
                content=f"{knowledge.title}: {knowledge.content[:400]}",
                metadata={
                    "kind": "knowledge_item",
                    "category": knowledge.category,
                    "knowledge_id": str(knowledge.id),
                    "source_artifact_id": str(knowledge.source_artifact_id)
                    if knowledge.source_artifact_id
                    else None,
                },
                importance=min(0.9, max(0.3, knowledge.confidence)),
                source="knowledge_migration",
                client_id=client_id or knowledge.client_id,
                project_id=project_id,
                session_id=session_id,
            )
        )

    return items
