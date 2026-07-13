import logging

from fastapi import APIRouter, Request, Response, status
from minio import Minio

from app.core.config import get_settings
from app.database.postgres import check_postgres
from app.database.qdrant import check_qdrant
from app.database.redis import check_redis

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

REQUIRED_SERVICES = ("postgres", "redis")
OPTIONAL_SERVICES = ("qdrant", "minio")


def check_minio() -> tuple[bool, str]:
    settings = get_settings()
    try:
        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        client.list_buckets()
        return True, "ok"
    except Exception as exc:
        logger.warning("MinIO health check failed: %s", exc)
        return False, str(exc)


async def build_readiness_payload(request: Request) -> dict:
    settings = get_settings()

    postgres_ok, postgres_msg = await check_postgres(settings)
    redis_ok, redis_msg = await check_redis(settings)
    qdrant_ok, qdrant_msg = check_qdrant(settings)
    minio_ok, minio_msg = check_minio()

    services = {
        "postgres": {"status": "up" if postgres_ok else "down", "detail": postgres_msg},
        "redis": {"status": "up" if redis_ok else "down", "detail": redis_msg},
        "qdrant": {"status": "up" if qdrant_ok else "down", "detail": qdrant_msg},
        "minio": {"status": "up" if minio_ok else "down", "detail": minio_msg},
    }

    required_up = all(services[name]["status"] == "up" for name in REQUIRED_SERVICES)
    optional_up = all(services[name]["status"] == "up" for name in OPTIONAL_SERVICES)
    if not required_up:
        overall = "not_ready"
    elif not optional_up:
        overall = "degraded"
    else:
        overall = "ready"

    trace_id = getattr(request.state, "trace_id", "-")

    return {
        "status": overall,
        "service": "ai-employee-os",
        "environment": settings.app_env,
        "trace_id": trace_id,
        "services": services,
        "required": list(REQUIRED_SERVICES),
        "optional": list(OPTIONAL_SERVICES),
    }


def build_liveness_payload(request: Request) -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "ai-employee-os",
        "environment": settings.app_env,
        "trace_id": getattr(request.state, "trace_id", "-"),
    }


# Backward-compatible alias used by older imports/tests.
async def build_health_payload(request: Request) -> dict:
    return await build_readiness_payload(request)


@router.get("/health")
async def health(request: Request) -> dict:
    """Liveness probe — process is up."""
    return build_liveness_payload(request)


@router.get("/ready")
async def ready(request: Request, response: Response) -> dict:
    """Readiness probe — required dependencies must be up; optional may degrade."""
    payload = await build_readiness_payload(request)
    if payload["status"] == "not_ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return payload
