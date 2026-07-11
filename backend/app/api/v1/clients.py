from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.dependencies import get_client_service
from app.schemas.client import ClientCreate, ClientRead, ClientUpdate
from app.services.client_service import ClientService

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=list[ClientRead])
async def list_clients(
    skip: int = 0,
    limit: int = 100,
    service: ClientService = Depends(get_client_service),
) -> list[ClientRead]:
    return await service.list_all(skip=skip, limit=limit)


@router.post("", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
async def create_client(
    data: ClientCreate,
    service: ClientService = Depends(get_client_service),
) -> ClientRead:
    return await service.create(data)


@router.get("/{client_id}", response_model=ClientRead)
async def get_client(
    client_id: UUID,
    service: ClientService = Depends(get_client_service),
) -> ClientRead:
    client = await service.get_by_id(client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return client


@router.patch("/{client_id}", response_model=ClientRead)
async def update_client(
    client_id: UUID,
    data: ClientUpdate,
    service: ClientService = Depends(get_client_service),
) -> ClientRead:
    client = await service.update(client_id, data)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: UUID,
    service: ClientService = Depends(get_client_service),
) -> None:
    deleted = await service.delete(client_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
