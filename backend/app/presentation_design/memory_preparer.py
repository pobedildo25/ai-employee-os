from uuid import UUID

from app.memory.models import MemoryItem, MemoryType
from app.presentation_design.models import PresentationDesignResult


def prepare_presentation_memory_items(
    result: PresentationDesignResult,
    *,
    client_id: UUID | str | None = None,
    project_id: UUID | str | None = None,
    session_id: str | None = None,
) -> list[MemoryItem]:
    if result.plan is None:
        return []
    return [
        MemoryItem(
            type=MemoryType.DECISION,
            content=(
                f"Presentation designed: '{result.plan.title}' "
                f"({result.plan.presentation_type.value}, {len(result.plan.slides)} slides)"
            ),
            metadata={
                "kind": "presentation_design",
                "presentation_type": result.plan.presentation_type.value,
                "slide_count": len(result.plan.slides),
            },
            importance=0.55,
            source="presentation_design",
            client_id=UUID(str(client_id)) if client_id else None,
            project_id=UUID(str(project_id)) if project_id else None,
            session_id=session_id,
        )
    ]
