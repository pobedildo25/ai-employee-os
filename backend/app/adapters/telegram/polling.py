"""Long-polling transport for Telegram (production, no webhook/domain required)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.adapters.telegram.bot import TelegramBot
from app.adapters.telegram.idempotency import claim_telegram_update
from app.bootstrap.telegram_app import build_telegram_bot
from app.core.config import get_settings
from app.database.session import get_session_factory

logger = logging.getLogger(__name__)

DbRelease = Callable[[], Awaitable[None]]


def _get_redis_optional():
    try:
        from app.core.config import get_settings as _gs
        from app.database.redis import get_redis_client

        return get_redis_client(_gs())
    except Exception as exc:
        logger.debug("telegram idempotency redis unavailable: %s", exc)
        return None


class TelegramPollingService:
    def __init__(self, *, poll_timeout: int = 25) -> None:
        self._poll_timeout = poll_timeout
        self._offset = 0
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._redis = None

    async def start(self) -> None:
        settings = get_settings()
        if not settings.telegram_enabled:
            logger.info("Telegram polling disabled (TELEGRAM_ENABLED=false)")
            return
        if not settings.telegram_bot_token:
            logger.warning("Telegram polling skipped: TELEGRAM_BOT_TOKEN is empty")
            return
        if self._task is not None and not self._task.done():
            return
        self._redis = _get_redis_optional()
        self._running = True
        self._task = asyncio.create_task(self._run_loop(settings.telegram_bot_token), name="telegram-polling")
        logger.info("Telegram long polling started")

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Telegram long polling stopped")

    async def _run_loop(self, token: str) -> None:
        api_base = f"https://api.telegram.org/bot{token}"
        session_factory = get_session_factory()
        timeout = httpx.Timeout(self._poll_timeout + 15.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            while self._running:
                try:
                    response = await client.get(
                        f"{api_base}/getUpdates",
                        params={"offset": self._offset, "timeout": self._poll_timeout},
                    )
                    payload = response.json()
                    if not payload.get("ok"):
                        logger.warning("telegram getUpdates failed: %s", payload.get("description", "unknown"))
                        await asyncio.sleep(3)
                        continue
                    for update in payload.get("result") or []:
                        if not isinstance(update, dict):
                            continue
                        update_id = update.get("update_id", self._offset)
                        self._offset = int(update_id) + 1
                        claimed = await claim_telegram_update(self._redis, update_id)
                        if not claimed:
                            logger.info("telegram duplicate update skipped | update_id=%s", update_id)
                            continue
                        await self._dispatch_update(session_factory, update)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.exception("telegram polling loop error: %s", exc)
                    await asyncio.sleep(5)

    async def _dispatch_update(self, session_factory, update: dict[str, Any]) -> None:
        """Handle one update without holding a DB transaction across LLM (P1-I).

        SQLAlchemy repos still need an AsyncSession for this process today, but we
        commit/release after short persistence bursts (resolve, history) via
        ``db_release`` so the connection is not held open for the entire LLM call.
        Final commit covers any trailing writes (artifacts, etc.).
        """
        async with session_factory() as session:
            async def db_release() -> None:
                if session.in_transaction():
                    await session.commit()

            try:
                bot: TelegramBot = build_telegram_bot(session, db_release=db_release)
                await bot.process_update(update)
                if session.in_transaction():
                    await session.commit()
            except Exception:
                if session.in_transaction():
                    await session.rollback()
                logger.exception(
                    "telegram update handling failed | update_id=%s",
                    update.get("update_id"),
                )
                raise


_polling_service: TelegramPollingService | None = None


def get_polling_service() -> TelegramPollingService:
    global _polling_service
    if _polling_service is None:
        _polling_service = TelegramPollingService()
    return _polling_service
