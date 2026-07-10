import logging

from fastapi import APIRouter, Request
from minio import Minio

from app.core.config import get_settings
from app.database.postgres import check_postgres
from app.database.qdrant import check_qdrant
from app.database.redis import check_redis

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


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


@router.get("/health")
async def health(request: Request) -> dict:
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

    all_up = all(s["status"] == "up" for s in services.values())
    trace_id = getattr(request.state, "trace_id", "-")

    return {
        "status": "ok" if all_up else "degraded",
        "service": "ai-employee-os",
        "environment": settings.app_env,
        "trace_id": trace_id,
        "services": services,
    }
