from app.knowledge.models import KnowledgeItem

DEFAULT_MIN_CONFIDENCE = 0.7
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


def select_items_for_persist(
    items: list[KnowledgeItem],
    *,
    persist: bool = False,
    confirm: bool = False,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    max_items: int = DEFAULT_MAX_ITEMS_PER_ARTIFACT,
) -> list[KnowledgeItem]:
    """Auto-remember gate: write only when persist/confirm and confidence is high enough.

    Default is persist=False (no store). Explicit confirm still requires non-empty
    title/content; confidence floor applies unless confirm is set.
    """
    if not persist and not confirm:
        return []
    floor = 0.0 if confirm else min_confidence
    return filter_items(items, min_confidence=floor, max_items=max_items)
