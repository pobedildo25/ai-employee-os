from uuid import UUID

from app.document_creation.models import DocumentCreationResult
from app.memory.models import MemoryItem, MemoryType


def prepare_document_creation_memory_items(
    result: DocumentCreationResult,
    *,
    client_id: UUID | None = None,
    project_id: UUID | None = None,
    session_id: str | None = None,
) -> list[MemoryItem]:
    """Prepare memory candidates from document creation without auto-saving."""
    items: list[MemoryItem] = []
    document_type = result.metadata.get("document_type", "unknown")
    title = result.metadata.get("title", "Document")

    if result.document_ast is not None:
        section_count = sum(
            1
            for node_type, count in (result.metadata.get("node_types") or {}).items()
            if node_type == "section"
        ) or len(
            [child for child in result.document_ast.root.children if child.node_type.value == "section"]
        )
        items.append(
            MemoryItem(
                type=MemoryType.FACT,
                content=f"Клиент использует структуру документов: {document_type} с разделами",
                metadata={
                    "kind": "document_creation_fact",
                    "document_type": document_type,
                    "title": title,
                    "node_count": result.document_ast.node_count,
                    "section_count": section_count,
                },
                importance=0.6,
                source="document_creation",
                client_id=client_id,
                project_id=project_id,
                session_id=session_id,
            )
        )

        headings = _collect_headings(result)
        if headings:
            items.append(
                MemoryItem(
                    type=MemoryType.KNOWLEDGE,
                    content=f"Предыдущие документы содержали разделы: {', '.join(headings[:5])}",
                    metadata={
                        "kind": "document_creation_knowledge",
                        "document_type": document_type,
                        "headings": headings[:5],
                    },
                    importance=0.5,
                    source="document_creation",
                    client_id=client_id,
                    project_id=project_id,
                    session_id=session_id,
                )
            )

    return items


def _collect_headings(result: DocumentCreationResult) -> list[str]:
    if result.document_ast is None:
        return []

    headings: list[str] = []

    def walk(node) -> None:
        if node.node_type.value == "heading" and node.content:
            headings.append(node.content)
        for child in node.children:
            walk(child)

    walk(result.document_ast.root)
    return headings
