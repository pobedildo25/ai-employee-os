from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_client_intelligence_manager, get_client_service
from app.client_intelligence.manager import ClientIntelligenceManager
from app.client_intelligence.models import ClientProfile
from app.clients.classification import is_telegram_user_client
from app.services.client_service import ClientService

router = APIRouter(prefix="/clients", tags=["client-intelligence"])


class ClientIntelligenceResponse(BaseModel):
    profile: ClientProfile
    confidence: float
    memory_candidates: list[dict[str, Any]] = Field(default_factory=list)
    analysis_warnings: list[str] = Field(default_factory=list)


class ClientIntelligenceAnalyzeRequest(BaseModel):
    use_llm: bool = True
    project_id: UUID | None = None
    user_input: str = ""
    context: dict[str, Any] = Field(default_factory=dict)


@router.get("/{client_id}/intelligence", response_model=ClientIntelligenceResponse)
async def get_client_intelligence(
    client_id: UUID,
    client_service: ClientService = Depends(get_client_service),
    manager: ClientIntelligenceManager = Depends(get_client_intelligence_manager),
) -> ClientIntelligenceResponse:
    client = await client_service.get_by_id(client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    if is_telegram_user_client(client):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram transport clients are excluded from client intelligence",
        )
    result = await manager.build_profile(client_id, use_llm=False)
    return ClientIntelligenceResponse(
        profile=result.profile,
        confidence=result.profile.confidence,
        memory_candidates=result.memory_candidates,
        analysis_warnings=result.analysis_warnings,
    )


@router.post(
    "/{client_id}/intelligence/analyze",
    response_model=ClientIntelligenceResponse,
)
async def analyze_client_intelligence(
    client_id: UUID,
    data: ClientIntelligenceAnalyzeRequest | None = None,
    client_service: ClientService = Depends(get_client_service),
    manager: ClientIntelligenceManager = Depends(get_client_intelligence_manager),
) -> ClientIntelligenceResponse:
    client = await client_service.get_by_id(client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    if is_telegram_user_client(client):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram transport clients are excluded from client intelligence",
        )
    payload = data or ClientIntelligenceAnalyzeRequest()
    result = await manager.build_profile(
        client_id,
        execution_context=payload.context,
        use_llm=payload.use_llm,
        project_id=payload.project_id,
        user_input=payload.user_input,
    )
    return ClientIntelligenceResponse(
        profile=result.profile,
        confidence=result.profile.confidence,
        memory_candidates=result.memory_candidates,
        analysis_warnings=result.analysis_warnings,
    )
