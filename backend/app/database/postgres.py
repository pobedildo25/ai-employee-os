import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import Settings

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None


def get_engine(settings: Settings) -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            echo=settings.app_debug,
        )
    return _engine


async def check_postgres(settings: Settings) -> tuple[bool, str]:
    try:
        engine = get_engine(settings)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:
        logger.warning("PostgreSQL health check failed: %s", exc)
        return False, str(exc)


async def close_postgres() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
