import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.logging import new_trace_id, setup_logging
from app.database.postgres import close_postgres
from app.database.qdrant import close_qdrant
from app.database.redis import close_redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Starting AI Employee OS backend (env=%s)", settings.app_env)
    yield
    await close_postgres()
    await close_redis()
    close_qdrant()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AI Employee OS",
        description="Agentic AI system for marketing agency",
        version="0.1.0",
        debug=settings.app_debug,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def trace_id_middleware(request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id") or new_trace_id()
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response

    app.include_router(health_router)
    return app


app = create_app()
