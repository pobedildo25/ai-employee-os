"""Long-polling transport for Telegram (production, no webhook/domain required)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.adapters.telegram.bot import TelegramBot
from app.bootstrap.telegram_app import build_telegram_bot
from app.core.config import get_settings
from app.database.session import get_session_factory

logger = logging.getLogger(__name__)


class TelegramPollingService:
    def __init__(self, *, poll_timeout: int = 25) -> None:
        self._poll_timeout = poll_timeout
        self._offset = 0
        self._running = False
        self._task: asyncio.Task[None] | None = None

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
                        self._offset = int(update.get("update_id", self._offset)) + 1
                        await self._dispatch_update(session_factory, update)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.exception("telegram polling loop error: %s", exc)
                    await asyncio.sleep(5)

    async def _dispatch_update(self, session_factory, update: dict[str, Any]) -> None:
        async with session_factory() as session:
            try:
                bot: TelegramBot = build_telegram_bot(session)
                await bot.process_update(update)
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception("telegram update handling failed | update_id=%s", update.get("update_id"))
                raise


_polling_service: TelegramPollingService | None = None


def get_polling_service() -> TelegramPollingService:
    global _polling_service
    if _polling_service is None:
        _polling_service = TelegramPollingService()
    return _polling_service
