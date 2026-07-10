from abc import ABC, abstractmethod
from typing import Any

from app.revision.models import RevisionRequest, RevisionResult


class RevisionInterface(ABC):
    @abstractmethod
    async def revise(
        self,
        request: RevisionRequest,
        *,
        document_ast: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        trace_id: str = "-",
    ) -> RevisionResult:
        """Apply revision based on quality feedback."""
