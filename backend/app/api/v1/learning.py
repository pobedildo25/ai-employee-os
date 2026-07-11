from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_learning_manager
from app.learning.manager import LearningManager
from app.learning.models import LearningRule, LearningSource

router = APIRouter(prefix="/learning", tags=["learning"])


class LearningFeedbackRequest(BaseModel):
    feedback: str = Field(min_length=1)
    client_id: UUID | None = None
    project_id: UUID | None = None
    source: LearningSource = LearningSource.EXPLICIT_PREFERENCE
    force: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.get("/rules", response_model=list[LearningRule])
async def list_learning_rules(
    client_id: UUID | None = Query(default=None),
    project_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    manager: LearningManager = Depends(get_learning_manager),
) -> list[LearningRule]:
    return await manager.get_rules(client_id=client_id, project_id=project_id, limit=limit)


@router.get("/rules/{client_id}", response_model=list[LearningRule])
async def list_learning_rules_for_client(
    client_id: UUID,
    limit: int = Query(default=100, ge=1, le=500),
    manager: LearningManager = Depends(get_learning_manager),
) -> list[LearningRule]:
    return await manager.get_rules(client_id=client_id, limit=limit)


@router.post("/feedback", response_model=LearningRule | None, status_code=status.HTTP_201_CREATED)
async def submit_learning_feedback(
    data: LearningFeedbackRequest,
    manager: LearningManager = Depends(get_learning_manager),
) -> LearningRule | None:
    rule = await manager.learn(
        data.feedback,
        source=data.source,
        client_id=data.client_id,
        project_id=data.project_id,
        context=data.metadata,
        force=data.force,
    )
    if rule is None and data.force:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Feedback did not produce a durable learning rule",
        )
    return rule
