import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api.health import router as health_router
from app.api.clients import router as clients_router
from app.api.projects import router as projects_router
from app.api.artifacts import router as artifacts_router
from app.api.tasks import router as tasks_router
from app.api.v1.router import api_router as api_v1_router
from app.core.config import Settings, get_settings
from app.core.logging import new_trace_id, setup_logging
from app.database.postgres import close_postgres
from app.database.qdrant import close_qdrant
from app.database.redis import close_redis
from app.security.interfaces.security import SecurityStore
from app.security.manager import SecurityManager
from app.security.middleware import SecurityMiddleware
from app.security.providers.in_memory_provider import InMemorySecurityProvider
from app.security.rate_limit import RateLimiter
from app.security.secrets import SecretsManager

logger = logging.getLogger(__name__)


def create_security_store(settings: Settings) -> SecurityStore:
    """Production prefers Redis-backed keys/audit; tests/dev keep InMemory."""
    if not settings.is_production:
        return InMemorySecurityProvider()
    try:
        from app.database.redis import get_redis_client
        from app.security.providers.redis_provider import RedisSecurityProvider

        return RedisSecurityProvider(get_redis_client(settings))
    except Exception as exc:
        logger.warning("Redis security store unavailable, using in-memory | error=%s", exc)
        return InMemorySecurityProvider()


def _build_security_manager(settings: Settings) -> SecurityManager:
    return SecurityManager(
        create_security_store(settings),
        rate_limiter=RateLimiter(
            limit=settings.security_rate_limit,
            window_seconds=settings.security_rate_window_seconds,
        ),
        secrets=SecretsManager(settings),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    if not hasattr(app.state, "security_manager"):
        app.state.security_manager = _build_security_manager(settings)
    logger.info("Starting AI Employee OS backend (env=%s)", settings.app_env)

    from app.adapters.telegram.polling import get_polling_service

    polling = get_polling_service()
    await polling.start()

    yield

    await polling.stop()
    await close_postgres()
    await close_redis()
    close_qdrant()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    security_manager = _build_security_manager(settings)
    is_production = settings.is_production
    app = FastAPI(
        title="AI Employee OS",
        description="Agentic AI system for marketing agency",
        version="0.1.0",
        debug=settings.app_debug and not is_production,
        lifespan=lifespan,
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
    )
    app.state.security_manager = security_manager

    @app.middleware("http")
    async def trace_id_middleware(request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id") or new_trace_id()
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response

    app.add_middleware(
        SecurityMiddleware,
        security_manager=security_manager,
        enabled=settings.security_enabled or is_production,
    )

    app.include_router(health_router)
    app.include_router(clients_router)
    app.include_router(projects_router)
    app.include_router(artifacts_router)
    app.include_router(tasks_router)
    app.include_router(api_v1_router, prefix="/api/v1")
    return app


app = create_app()
