import json
from typing import Any
from uuid import UUID

from app.agents.parsers.response_parser import ResponseParseError, extract_json_content
from app.knowledge.models import KnowledgeItem


def parse_knowledge_response(
    raw: str,
    *,
    client_id: UUID | None = None,
    source_artifact_id: UUID | None = None,
) -> list[KnowledgeItem]:
    content = extract_json_content(raw)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ResponseParseError(f"Invalid JSON: {exc}") from exc

    items_raw = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items_raw, list):
        raise ResponseParseError("Knowledge response must contain an items list")

    items: list[KnowledgeItem] = []
    for entry in items_raw:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or "").strip()
        body = str(entry.get("content") or "").strip()
        if not title or not body:
            continue
        confidence = float(entry.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
        items.append(
            KnowledgeItem(
                client_id=client_id,
                title=title,
                category=str(entry.get("category") or "general"),
                content=body,
                confidence=confidence,
                source_artifact_id=source_artifact_id,
                metadata=dict(entry.get("metadata") or {}),
            )
        )
    return items
