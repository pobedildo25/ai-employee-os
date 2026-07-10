from abc import ABC, abstractmethod


class StorageInterface(ABC):
    @abstractmethod
    async def upload(self, path: str, data: bytes, content_type: str | None = None) -> str:
        """Upload file and return storage path."""
        ...

    @abstractmethod
    async def download(self, path: str) -> bytes:
        """Download file content by storage path."""
        ...

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """Delete file by storage path."""
        ...

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if file exists at storage path."""
        ...
