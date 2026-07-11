from app.knowledge.models import KnowledgeItem

DEFAULT_MIN_CONFIDENCE = 0.4
DEFAULT_MAX_ITEMS_PER_ARTIFACT = 20


def should_persist_item(item: KnowledgeItem, *, min_confidence: float = DEFAULT_MIN_CONFIDENCE) -> bool:
    if not item.title.strip() or not item.content.strip():
        return False
    return item.confidence >= min_confidence


def filter_items(
    items: list[KnowledgeItem],
    *,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    max_items: int = DEFAULT_MAX_ITEMS_PER_ARTIFACT,
) -> list[KnowledgeItem]:
    filtered = [item for item in items if should_persist_item(item, min_confidence=min_confidence)]
    filtered.sort(key=lambda item: item.confidence, reverse=True)
    return filtered[:max_items]
