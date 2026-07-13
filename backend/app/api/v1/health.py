from fastapi import APIRouter, Request, Response, status

from app.api.health import build_liveness_payload, build_readiness_payload

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_v1(request: Request) -> dict:
    return build_liveness_payload(request)


@router.get("/ready")
async def ready_v1(request: Request, response: Response) -> dict:
    payload = await build_readiness_payload(request)
    if payload["status"] == "not_ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return payload
