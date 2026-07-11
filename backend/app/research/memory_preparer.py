from uuid import UUID

from app.memory.models import MemoryItem, MemoryType
from app.research.models import ResearchResult


def prepare_research_memory_items(
    result: ResearchResult,
    *,
    client_id: UUID | str | None = None,
    session_id: str | None = None,
) -> list[MemoryItem]:
    """Prepare memory/knowledge candidates — never auto-saves."""
    client_uuid = _as_uuid(client_id)
    items: list[MemoryItem] = [
        MemoryItem(
            type=MemoryType.KNOWLEDGE,
            content=result.summary or f"Research completed for '{result.query}'",
            metadata={
                "kind": "research",
                "research_id": str(result.id),
                "research_type": result.research_type.value,
                "confidence": result.confidence,
            },
            importance=0.6,
            source="research",
            client_id=client_uuid,
            session_id=session_id,
        )
    ]
    for insight in result.insights[:3]:
        items.append(
            MemoryItem(
                type=MemoryType.KNOWLEDGE,
                content=f"{insight.title}: {insight.description}",
                metadata={
                    "kind": "research_insight",
                    "category": insight.category,
                    "research_id": str(result.id),
                },
                importance=min(0.85, max(0.4, insight.importance)),
                source="research",
                client_id=client_uuid,
                session_id=session_id,
            )
        )
    for finding in result.findings[:2]:
        items.append(
            MemoryItem(
                type=MemoryType.FACT,
                content=f"{finding.title}: {finding.description}",
                metadata={"kind": "research_finding", "research_id": str(result.id)},
                importance=0.55,
                source="research",
                client_id=client_uuid,
                session_id=session_id,
            )
        )
    return items


def _as_uuid(value: UUID | str | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError:
        return None
