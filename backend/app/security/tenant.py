"""Minimal tenant ACL helpers based on API key metadata.client_id."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from app.security.models import Role, SecurityPrincipal


def scoped_client_id(principal: SecurityPrincipal | None) -> UUID | None:
    """Return tenant client scope, or None for full access (ADMIN / unscoped)."""
    if principal is None:
        return None
    if principal.role == Role.ADMIN:
        return None
    return principal.client_id


def enforce_client_access(
    principal: SecurityPrincipal | None,
    resource_client_id: UUID | None,
    *,
    detail: str = "Forbidden for this tenant",
) -> None:
    """Fail closed: scoped keys may only touch their client_id."""
    scoped = scoped_client_id(principal)
    if scoped is None:
        return
    if resource_client_id is None or resource_client_id != scoped:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def parse_client_id_from_metadata(metadata: dict | None) -> UUID | None:
    if not metadata:
        return None
    raw = metadata.get("client_id") or metadata.get("tenant_client_id")
    if raw is None or raw == "":
        return None
    try:
        return UUID(str(raw))
    except (TypeError, ValueError):
        return None
