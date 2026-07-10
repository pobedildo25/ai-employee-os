from abc import ABC, abstractmethod

from app.document_creation.models import DocumentCreationRequest, DocumentCreationResult


class DocumentCreatorInterface(ABC):
    @abstractmethod
    async def create(
        self,
        request: DocumentCreationRequest,
        *,
        available_capabilities: list[dict[str, str]] | None = None,
        trace_id: str = "-",
    ) -> DocumentCreationResult:
        """Create document AST from user intent."""
