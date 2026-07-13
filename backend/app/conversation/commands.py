"""Channel-neutral slash-command parsing for conversation control."""

from __future__ import annotations

import re
from enum import Enum


class SlashCommand(str, Enum):
    NEW = "new"
    STATUS = "status"
    CANCEL = "cancel"
    START = "start"


_COMMAND_RE = re.compile(
    r"^/(?P<cmd>new|status|cancel|start)(?:@(?P<bot>\S+))?(?:\s|$)",
    re.IGNORECASE,
)


def parse_slash_command(text: str | None) -> SlashCommand | None:
    """Parse a leading slash command; strip optional Telegram @botname suffix."""
    if not text:
        return None
    match = _COMMAND_RE.match(text.strip())
    if match is None:
        return None
    try:
        return SlashCommand(match.group("cmd").lower())
    except ValueError:
        return None
