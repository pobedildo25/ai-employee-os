from app.memory.models import MemoryItem, MemoryType

PERSISTABLE_TYPES: frozenset[MemoryType] = frozenset(
    {
        MemoryType.FACT,
        MemoryType.PREFERENCE,
        MemoryType.DECISION,
        MemoryType.KNOWLEDGE,
    }
)

EPHEMERAL_METADATA_FLAGS = frozenset({"ephemeral", "temporary", "chat_only"})


def should_persist(item: MemoryItem) -> bool:
    """Return True when a memory item is eligible for storage."""
    if item.type == MemoryType.SHORT_TERM:
        return True

    if item.type not in PERSISTABLE_TYPES:
        return False

    if item.importance <= 0:
        return False

    if _is_ephemeral(item):
        return False

    return True


def is_retained_type(memory_type: MemoryType) -> bool:
    """Return True for long-lived memory types."""
    return memory_type in PERSISTABLE_TYPES


def _is_ephemeral(item: MemoryItem) -> bool:
    if item.metadata.get("ephemeral") is True:
        return True
    kind = item.metadata.get("kind")
    if kind in {"chat", "chat_message", "one_time"}:
        return True
    if any(item.metadata.get(flag) for flag in EPHEMERAL_METADATA_FLAGS):
        return True
    return False
