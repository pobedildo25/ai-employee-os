from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_research_manager
from app.core.config import get_settings
from app.research.manager import ResearchManager
from app.research.models import ResearchRequest, ResearchResult, ResearchType

router = APIRouter(prefix="/research", tags=["research"])


class ResearchRunRequest(BaseModel):
    query: str = Field(min_length=1)
    type: ResearchType | str = ResearchType.MARKET_RESEARCH
    research_type: ResearchType | str | None = None
    client_id: UUID | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    max_sources: int = Field(default=8, ge=1, le=50)


def _require_research_enabled() -> None:
    settings = get_settings()
    if not settings.research_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Research capability is disabled",
        )
    from app.core.feature_guards import OptionalStackMisconfigured, validate_optional_stacks

    try:
        validate_optional_stacks(settings)
    except OptionalStackMisconfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


def _get_enabled_research_manager(
    _: None = Depends(_require_research_enabled),
    manager: ResearchManager | None = Depends(get_research_manager),
) -> ResearchManager:
    """Fail closed: research routes never run with an absent/mock-off manager."""
    if manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Research capability is disabled",
        )
    return manager


@router.post("/run", response_model=ResearchResult)
async def run_research(
    data: ResearchRunRequest,
    manager: ResearchManager = Depends(_get_enabled_research_manager),
) -> ResearchResult:
    type_raw = data.research_type or data.type
    try:
        research_type = ResearchType(str(type_raw).upper())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown research type: {type_raw}",
        ) from exc

    return await manager.run(
        ResearchRequest(
            query=data.query,
            research_type=research_type,
            client_id=data.client_id,
            context=data.context,
            constraints=data.constraints,
            learning_rules=list(
                data.context.get("learning_context") or data.context.get("learning_rules") or []
            ),
            max_sources=data.max_sources,
        )
    )


@router.get("/{research_id}", response_model=ResearchResult)
async def get_research(
    research_id: UUID,
    manager: ResearchManager = Depends(_get_enabled_research_manager),
) -> ResearchResult:
    result = manager.get_result(str(research_id))
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research not found")
    return result
