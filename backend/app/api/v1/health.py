from fastapi import APIRouter, Request

from app.api.health import build_health_payload

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_v1(request: Request) -> dict:
    return await build_health_payload(request)
