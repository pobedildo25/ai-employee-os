from fastapi import APIRouter, status

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def list_clients() -> dict[str, str]:
    return {"detail": "Not implemented"}


@router.post("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def create_client() -> dict[str, str]:
    return {"detail": "Not implemented"}


@router.get("/{client_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_client(client_id: str) -> dict[str, str]:
    return {"detail": "Not implemented"}


@router.patch("/{client_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def update_client(client_id: str) -> dict[str, str]:
    return {"detail": "Not implemented"}


@router.delete("/{client_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def delete_client(client_id: str) -> dict[str, str]:
    return {"detail": "Not implemented"}
