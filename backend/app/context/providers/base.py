from abc import ABC, abstractmethod
from typing import Any

from app.context.models import ContextRequest


class ContextProvider(ABC):
    """Base interface for independent context data providers."""

    name: str

    @abstractmethod
    async def fetch(self, request: ContextRequest) -> dict[str, Any]:
        """Fetch a partial context fragment. Returns empty dict when not applicable."""
