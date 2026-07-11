from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_analytics_manager, get_client_service
from app.analytics.manager import AnalyticsManager
from app.analytics.models import AnalyticsInsight, AnalyticsRequest, AnalyticsType
from app.clients.classification import is_telegram_user_client
from app.services.client_service import ClientService

router = APIRouter(prefix="/analytics", tags=["analytics"])


class AnalyticsRunRequest(BaseModel):
    type: AnalyticsType | str = AnalyticsType.CLIENT_PERFORMANCE
    analytics_type: AnalyticsType | str | None = None
    client_id: UUID | None = None
    project_id: UUID | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    goal: str | None = None
    use_llm: bool = True


class AnalyticsRunResponse(BaseModel):
    summary: str
    metrics: dict[str, Any]
    insights: list[AnalyticsInsight]
    recommendations: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    document_ast: dict[str, Any] | None = None
    memory_candidates: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/run", response_model=AnalyticsRunResponse)
async def run_analytics(
    data: AnalyticsRunRequest,
    manager: AnalyticsManager = Depends(get_analytics_manager),
) -> AnalyticsRunResponse:
    type_raw = data.analytics_type or data.type
    try:
        analytics_type = AnalyticsType(str(type_raw).upper())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown analytics type: {type_raw}",
        ) from exc

    result = await manager.run(
        AnalyticsRequest(
            analytics_type=analytics_type,
            client_id=data.client_id,
            project_id=data.project_id,
            filters=data.filters,
            context=data.context,
            goal=data.goal,
            learning_rules=list(
                data.context.get("learning_context") or data.context.get("learning_rules") or []
            ),
        )
    )
    return AnalyticsRunResponse(
        summary=result.summary,
        metrics=result.metrics,
        insights=result.insights,
        recommendations=result.recommendations,
        confidence=result.confidence,
        document_ast=result.document_ast,
        memory_candidates=result.memory_candidates,
    )


@router.get("/client/{client_id}", response_model=AnalyticsRunResponse)
async def get_client_analytics(
    client_id: UUID,
    client_service: ClientService = Depends(get_client_service),
    manager: AnalyticsManager = Depends(get_analytics_manager),
) -> AnalyticsRunResponse:
    client = await client_service.get_by_id(client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    if is_telegram_user_client(client):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram transport clients are excluded from business analytics",
        )
    result = await manager.run(
        AnalyticsRequest(
            analytics_type=AnalyticsType.CLIENT_PERFORMANCE,
            client_id=client_id,
            context={"client_context": {"id": str(client.id), "name": client.name}},
        )
    )
    return AnalyticsRunResponse(
        summary=result.summary,
        metrics=result.metrics,
        insights=result.insights,
        recommendations=result.recommendations,
        confidence=result.confidence,
        document_ast=result.document_ast,
        memory_candidates=result.memory_candidates,
    )
