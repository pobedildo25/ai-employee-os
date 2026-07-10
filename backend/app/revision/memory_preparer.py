from uuid import UUID

from app.memory.models import MemoryItem, MemoryType
from app.revision.models import RevisionRequest, RevisionResult


def prepare_revision_memory_items(
    request: RevisionRequest,
    result: RevisionResult,
    *,
    client_id: UUID | None = None,
    project_id: UUID | None = None,
    session_id: str | None = None,
) -> list[MemoryItem]:
    """Prepare memory candidates from revision without auto-saving."""
    items: list[MemoryItem] = []

    if request.user_feedback:
        items.append(
            MemoryItem(
                type=MemoryType.FACT,
                content=f"Пользователь предпочитает: {request.user_feedback[:300]}",
                metadata={
                    "kind": "revision_preference",
                    "revision_count": request.revision_count,
                },
                importance=0.6,
                source="revision",
                client_id=client_id,
                project_id=project_id,
                session_id=session_id,
            )
        )

    if result.changes_applied:
        items.append(
            MemoryItem(
                type=MemoryType.KNOWLEDGE,
                content=(
                    "В прошлых ревизиях применялись изменения: "
                    + "; ".join(result.changes_applied[:5])
                ),
                metadata={
                    "kind": "revision_knowledge",
                    "status": result.status.value,
                    "changes": result.changes_applied[:5],
                },
                importance=0.5,
                source="revision",
                client_id=client_id,
                project_id=project_id,
                session_id=session_id,
            )
        )

    return items
