from abc import ABC, abstractmethod
from typing import Any

from app.quality.models import ReviewResult


class ReviewerInterface(ABC):
    @abstractmethod
    async def review(self, context: dict[str, Any], *, trace_id: str = "-") -> ReviewResult:
        """Review execution output against user goal and context."""
