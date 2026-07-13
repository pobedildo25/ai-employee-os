from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.v1.dependencies import get_client_service
from app.schemas.client import ClientCreate, ClientRead, ClientUpdate
from app.security.models import SecurityPrincipal
from app.security.tenant import enforce_client_access, scoped_client_id
from app.services.client_service import ClientService

router = APIRouter(prefix="/clients", tags=["clients"])


def _principal(request: Request) -> SecurityPrincipal | None:
    return getattr(request.state, "principal", None)


@router.get("", response_model=list[ClientRead])
async def list_clients(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    service: ClientService = Depends(get_client_service),
) -> list[ClientRead]:
    principal = _principal(request)
    scoped = scoped_client_id(principal)
    if scoped is not None:
        client = await service.get_by_id(scoped)
        return [client] if client is not None else []
    return await service.list_all(skip=skip, limit=limit)


@router.post("", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
async def create_client(
    request: Request,
    data: ClientCreate,
    service: ClientService = Depends(get_client_service),
) -> ClientRead:
    # Scoped keys cannot create arbitrary tenants.
    if scoped_client_id(_principal(request)) is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Scoped API key cannot create clients",
        )
    return await service.create(data)


@router.get("/{client_id}", response_model=ClientRead)
async def get_client(
    request: Request,
    client_id: UUID,
    service: ClientService = Depends(get_client_service),
) -> ClientRead:
    enforce_client_access(_principal(request), client_id)
    client = await service.get_by_id(client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return client


@router.patch("/{client_id}", response_model=ClientRead)
async def update_client(
    request: Request,
    client_id: UUID,
    data: ClientUpdate,
    service: ClientService = Depends(get_client_service),
) -> ClientRead:
    enforce_client_access(_principal(request), client_id)
    client = await service.update(client_id, data)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    request: Request,
    client_id: UUID,
    service: ClientService = Depends(get_client_service),
) -> None:
    enforce_client_access(_principal(request), client_id)
    deleted = await service.delete(client_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
