"""Post-action durable memory persistence (not a decision / keyword router).

Product Decision stays with Executive. This module only persists
``memory_candidates`` already emitted by skills / runtime after a successful
action. No regex / imperative routing on raw user text.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from app.memory.manager import MemoryManager, MemoryRetentionError
from app.memory.models import MemoryItem, MemoryType

logger = logging.getLogger(__name__)

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

    async def capture(
        self,
        fact: str,
        *,
        client_id: str | UUID | None = None,
        project_id: str | UUID | None = None,
        session_id: str | None = None,
        source: str = "user",
    ) -> MemoryCaptureResult:
        """Persist an already-decided fact (caller must not use keyword routing)."""
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
            metadata={"kind": "user_note", "captured_from": "post_action"},
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

    async def persist_candidates(self, candidates: list[dict]) -> int:
        """Persist memory_candidates emitted by skills (retention-filtered, deduped).

        Post-action hook after a successful run — never a pre-Executive router.
        """
        if not self._memory.enabled or not candidates:
            return 0
        stored = 0
        seen: set[tuple[str, str]] = set()
        for raw in candidates:
            if not isinstance(raw, dict):
                continue
            try:
                item = MemoryItem.model_validate(raw)
            except Exception:
                continue
            key = (item.type.value, item.content.strip().lower())
            if not item.content.strip() or key in seen:
                continue
            seen.add(key)
            try:
                await self._memory.remember(item)
                stored += 1
            except MemoryRetentionError:
                continue
            except Exception as exc:
                logger.warning("failed to persist memory candidate | error=%s", exc)
        if stored:
            logger.info("persisted memory candidates | count=%d", stored)
        return stored


def _as_uuid(value: str | UUID | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None
