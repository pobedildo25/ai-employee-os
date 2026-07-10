"""Estimate token count for text and messages."""


def count_tokens(text: str, model: str | None = None) -> int:
    """Estimate token count for the given text.

    Real tokenizer integration will be added in a later stage.
    """
    if not text:
        return 0
    _ = model
    return max(1, len(text) // 4)


def count_messages_tokens(messages: list[dict[str, str]], model: str | None = None) -> int:
    """Estimate token count for a list of chat messages."""
    total = 0
    for message in messages:
        total += count_tokens(message.get("content", ""), model=model)
        total += 4
    return total
