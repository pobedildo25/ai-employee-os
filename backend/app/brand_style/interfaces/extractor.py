from abc import ABC, abstractmethod
from typing import Any

from app.document_intelligence.models import DocumentRepresentation


class StyleExtractor(ABC):
    @abstractmethod
    def extract(
        self,
        document_representation: DocumentRepresentation,
        *,
        file_bytes: bytes | None = None,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """Extract raw brand style data from a document representation."""
