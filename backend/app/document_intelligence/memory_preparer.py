from uuid import UUID

from app.document_intelligence.models import DocumentRepresentation
from app.memory.models import MemoryItem, MemoryType


def prepare_document_memory_items(
    representation: DocumentRepresentation,
    *,
    client_id: UUID | None = None,
    project_id: UUID | None = None,
    session_id: str | None = None,
) -> list[MemoryItem]:
    """Prepare memory candidates from a document representation without auto-saving."""
    items: list[MemoryItem] = []

    structure_summary = (
        f"Document '{representation.title}' "
        f"({representation.document_type}): "
        f"{representation.structure.get('node_count', 0)} nodes, "
        f"{len(representation.elements)} elements"
    )
    items.append(
        MemoryItem(
            type=MemoryType.FACT,
            content=structure_summary,
            metadata={
                "artifact_id": str(representation.artifact_id),
                "document_type": representation.document_type,
                "ast_reference": representation.ast_reference,
                "kind": "document_structure",
            },
            importance=0.6,
            source="document_intelligence",
            client_id=client_id,
            project_id=project_id,
            session_id=session_id,
        )
    )

    for element in representation.elements[:5]:
        if not element.content:
            continue
        items.append(
            MemoryItem(
                type=MemoryType.KNOWLEDGE,
                content=f"{representation.title}: {element.content[:500]}",
                metadata={
                    "artifact_id": str(representation.artifact_id),
                    "element_type": element.element_type,
                    "kind": "document_element",
                },
                importance=0.4,
                source="document_intelligence",
                client_id=client_id,
                project_id=project_id,
                session_id=session_id,
            )
        )

    return items
