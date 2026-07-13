from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.api.deps import get_security_manager
from app.core.config import get_settings
from app.security.manager import SecurityManager
from app.security.models import APIKeyCreateResult, APIKeyInfo, AuditEvent, Role
from app.security.permissions import SECURITY_AUDIT_READ, SECURITY_KEYS_MANAGE

router = APIRouter(prefix="/security", tags=["security"])


class CreateAPIKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    role: Role = Role.USER
    permissions: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def _principal(request: Request):
    return getattr(request.state, "principal", None)


def _is_anonymous(principal) -> bool:
    return principal is None or getattr(principal, "actor", "anonymous") == "anonymous"


def _require_keys_manage_when_secured(request: Request, manager: SecurityManager) -> None:
    settings = get_settings()
    principal = _principal(request)
    secured = settings.security_enabled or settings.is_production
    if secured:
        if _is_anonymous(principal):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        if not manager.check_permission(principal, SECURITY_KEYS_MANAGE):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return
    if principal is not None and not _is_anonymous(principal):
        if not manager.check_permission(principal, SECURITY_KEYS_MANAGE):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


@router.post("/keys", response_model=APIKeyCreateResult, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: CreateAPIKeyRequest,
    request: Request,
    manager: SecurityManager = Depends(get_security_manager),
) -> APIKeyCreateResult:
    principal = _principal(request)
    if data.role == Role.ADMIN and _is_anonymous(principal):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Anonymous ADMIN key creation is not allowed",
        )
    _require_keys_manage_when_secured(request, manager)

    created = await manager.create_api_key(
        name=data.name,
        role=data.role,
        permissions=data.permissions,
        metadata=data.metadata,
    )
    await manager.record_audit(
        actor=getattr(principal, "actor", "anonymous"),
        action="security.keys.create",
        resource=f"security/keys/{created.id}",
        trace_id=getattr(request.state, "trace_id", "-"),
        metadata={"name": data.name, "role": data.role.value},
    )
    return created


@router.get("/keys", response_model=list[APIKeyInfo])
async def list_api_keys(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    manager: SecurityManager = Depends(get_security_manager),
) -> list[APIKeyInfo]:
    _require_keys_manage_when_secured(request, manager)
    return await manager.list_keys(limit=limit)


@router.delete("/keys/{key_id}", response_model=APIKeyInfo)
async def revoke_api_key(
    key_id: UUID,
    request: Request,
    manager: SecurityManager = Depends(get_security_manager),
) -> APIKeyInfo:
    principal = _principal(request)
    _require_keys_manage_when_secured(request, manager)

    revoked = await manager.revoke_api_key(key_id)
    if revoked is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    await manager.record_audit(
        actor=getattr(principal, "actor", "anonymous"),
        action="security.keys.revoke",
        resource=f"security/keys/{key_id}",
        trace_id=getattr(request.state, "trace_id", "-"),
    )
    return revoked


@router.get("/audit", response_model=list[AuditEvent])
async def list_audit_events(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    manager: SecurityManager = Depends(get_security_manager),
) -> list[AuditEvent]:
    settings = get_settings()
    principal = _principal(request)
    secured = settings.security_enabled or settings.is_production
    if secured:
        if _is_anonymous(principal):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        if not manager.check_permission(principal, SECURITY_AUDIT_READ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    elif principal is not None and not _is_anonymous(principal):
        if not manager.check_permission(principal, SECURITY_AUDIT_READ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    return await manager.list_audit(limit=limit)
