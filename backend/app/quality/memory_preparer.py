from uuid import UUID

from app.quality.models import ReviewResult
from app.memory.models import MemoryItem, MemoryType


def prepare_quality_memory_items(
    review: ReviewResult,
    *,
    user_goal: str,
    client_id: UUID | None = None,
    project_id: UUID | None = None,
    session_id: str | None = None,
) -> list[MemoryItem]:
    """Prepare memory candidates from quality review without auto-saving."""
    items: list[MemoryItem] = []

    if review.status.value == "PASS":
        items.append(
            MemoryItem(
                type=MemoryType.FACT,
                content=f"Пользователь предпочитает такой формат результата для цели: {user_goal[:200]}",
                metadata={
                    "kind": "quality_preference",
                    "review_status": review.status.value,
                    "score": review.score,
                },
                importance=0.5,
                source="quality_gate",
                client_id=client_id,
                project_id=project_id,
                session_id=session_id,
            )
        )

    if review.issues or review.recommendations:
        requirement_parts = [issue.description for issue in review.issues[:3]]
        requirement_parts.extend(review.recommendations[:2])
        if requirement_parts:
            items.append(
                MemoryItem(
                    type=MemoryType.KNOWLEDGE,
                    content=f"Для клиента важны такие требования качества: {'; '.join(requirement_parts)}",
                    metadata={
                        "kind": "quality_knowledge",
                        "review_status": review.status.value,
                        "issue_count": len(review.issues),
                    },
                    importance=0.6,
                    source="quality_gate",
                    client_id=client_id,
                    project_id=project_id,
                    session_id=session_id,
                )
            )

    return items
