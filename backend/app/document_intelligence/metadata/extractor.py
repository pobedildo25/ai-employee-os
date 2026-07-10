from typing import Any

from app.document_intelligence.ast.models import ASTNode, ASTNodeType
from app.document_intelligence.models import DocumentElement
from app.file_processing.models import ExtractedContent, FileCategory


def extract_document_metadata(
    *,
    title: str,
    extracted: ExtractedContent,
) -> dict[str, Any]:
    category = extracted.metadata.get("category", FileCategory.UNKNOWN.value)
    metadata: dict[str, Any] = {
        "filename": extracted.metadata.get("filename"),
        "mime_type": extracted.metadata.get("mime_type"),
        "extension": extracted.metadata.get("extension"),
        "format": extracted.metadata.get("format"),
        "category": category,
    }
    if extracted.pages is not None:
        metadata["pages"] = extracted.pages
    if extracted.tables is not None:
        metadata["table_count"] = len(extracted.tables)
    if title:
        metadata["title"] = title
    return metadata


def infer_document_type(extracted: ExtractedContent) -> str:
    category = extracted.metadata.get("category")
    if category:
        return str(category)
    file_format = extracted.metadata.get("format")
    if file_format:
        return str(file_format)
    return FileCategory.UNKNOWN.value
