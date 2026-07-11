from uuid import UUID

from app.analytics.models import AnalyticsResult
from app.memory.models import MemoryItem, MemoryType


def prepare_analytics_memory_items(
    result: AnalyticsResult,
    *,
    client_id: UUID | str | None = None,
    project_id: UUID | str | None = None,
    session_id: str | None = None,
) -> list[MemoryItem]:
    client_uuid = _as_uuid(client_id)
    project_uuid = _as_uuid(project_id)
    items: list[MemoryItem] = [
        MemoryItem(
            type=MemoryType.DECISION,
            content=f"Analytics ({result.analytics_type.value}): {(result.summary or '')[:180]}",
            metadata={
                "kind": "analytics",
                "analytics_type": result.analytics_type.value,
                "confidence": result.confidence,
            },
            importance=0.55,
            source="analytics",
            client_id=client_uuid,
            project_id=project_uuid,
            session_id=session_id,
        )
    ]
    for insight in result.insights[:3]:
        items.append(
            MemoryItem(
                type=MemoryType.FACT,
                content=f"{insight.title}: {insight.description}",
                metadata={
                    "kind": "analytics_insight",
                    "category": insight.category,
                    "confidence": insight.confidence,
                },
                importance=min(0.85, max(0.4, insight.importance)),
                source="analytics",
                client_id=client_uuid,
                project_id=project_uuid,
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
