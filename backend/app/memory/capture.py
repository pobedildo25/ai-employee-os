"""Capture explicit "запомни, что…" notes from dialogue into durable memory.

Users expect a ChatGPT-like assistant to remember things they tell it between
sessions. This detects an explicit imperative to remember, extracts the fact,
and persists it as a durable FACT/PREFERENCE (Postgres long-term memory), so it
is recalled into context on future turns via the MemoryContextProvider.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from uuid import UUID

from app.memory.manager import MemoryManager
from app.memory.models import MemoryItem, MemoryType

logger = logging.getLogger(__name__)

# Leading imperative markers that mean "store this".
_IMPERATIVE_PATTERN = re.compile(
    r"^\s*(?:запомни|запиши|заметь|не\s+забудь|имей\s+в\s+виду|remember|note)"
    r"[\s,:—-]*(?:что|then|that)?[\s,:—-]*",
    re.IGNORECASE,
)

_PREFERENCE_MARKERS = (
    "предпочит",
    "нравится",
    "не нравится",
    "люблю",
    "не люблю",
    "всегда",
    "никогда",
    "prefer",
    "always",
    "never",
)


@dataclass(frozen=True)
class MemoryCaptureResult:
    stored: bool
    content: str
    reply: str


class DialogueMemoryCapture:
    def __init__(self, memory_manager: MemoryManager) -> None:
        self._memory = memory_manager

    def detect(self, text: str) -> str | None:
        """Return the fact to remember when the message is a remember-imperative."""
        if not text:
            return None
        match = _IMPERATIVE_PATTERN.match(text)
        if not match:
            return None
        fact = text[match.end() :].strip().strip("\"'«»").strip()
        # Require some substance beyond the bare command word.
        if len(fact) < 3:
            return None
        return fact

    async def capture(
        self,
        fact: str,
        *,
        client_id: str | UUID | None = None,
        project_id: str | UUID | None = None,
        session_id: str | None = None,
        source: str = "user",
    ) -> MemoryCaptureResult:
        if not self._memory.enabled:
            return MemoryCaptureResult(
                stored=False,
                content=fact,
                reply="Память сейчас отключена, не могу сохранить.",
            )

        memory_type = (
            MemoryType.PREFERENCE
            if any(marker in fact.lower() for marker in _PREFERENCE_MARKERS)
            else MemoryType.FACT
        )
        item = MemoryItem(
            type=memory_type,
            content=fact,
            importance=0.8,
            source=source,
            client_id=_as_uuid(client_id),
            project_id=_as_uuid(project_id),
            session_id=session_id,
            metadata={"kind": "user_note", "captured_from": "dialogue"},
        )
        try:
            await self._memory.remember(item)
        except Exception as exc:
            logger.warning("failed to persist dialogue memory | error=%s", exc)
            return MemoryCaptureResult(
                stored=False,
                content=fact,
                reply="Не удалось сохранить в память, попробуйте ещё раз.",
            )

        logger.info("dialogue memory captured | type=%s client_id=%s", memory_type.value, client_id)
        return MemoryCaptureResult(stored=True, content=fact, reply=f"Запомнил: {fact}")


def _as_uuid(value: str | UUID | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None
