import re

_REVISION_HINTS = re.compile(
    r"(сделай|измени|добавь|убери|короче|длиннее|переделай|исправь|стиль|структур|раздел|объ[её]м|таблиц)",
    re.IGNORECASE,
)


def is_contextual_revision_message(text: str) -> bool:
    """Detect revision intent only for post-result user messages — not executive routing."""
    normalized = text.strip()
    if len(normalized) < 4:
        return False
    return bool(_REVISION_HINTS.search(normalized))
