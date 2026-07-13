"""Standalone Telegram long-polling worker (no FastAPI HTTP).

Usage:
  python -m app.adapters.telegram.worker
"""

from __future__ import annotations

import asyncio
import logging
import signal

from app.adapters.telegram.polling import get_polling_service
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.database.postgres import close_postgres
from app.database.qdrant import close_qdrant
from app.database.redis import close_redis

logger = logging.getLogger(__name__)


async def run_worker() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    if not settings.telegram_enabled:
        logger.error("TELEGRAM_ENABLED=false — telegram worker exiting")
        return
    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is empty — telegram worker exiting")
        return

    polling = get_polling_service()
    await polling.start()
    logger.info("Telegram worker running (inline_polling flag ignored; this process is the worker)")

    stop = asyncio.Event()

    def _request_stop(*_args: object) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except (NotImplementedError, RuntimeError):
            # Windows / limited environments
            signal.signal(sig, lambda *_: _request_stop())

    await stop.wait()
    await polling.stop()
    await close_postgres()
    await close_redis()
    close_qdrant()
    logger.info("Telegram worker shutdown complete")


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
