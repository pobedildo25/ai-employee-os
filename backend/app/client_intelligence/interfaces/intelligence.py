from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from app.client_intelligence.models import (
    ClientIntelligenceResult,
    ClientIntelligenceSources,
    ClientProfile,
)


class ClientIntelligenceBuilderInterface(ABC):
    @abstractmethod
    def build(self, sources: ClientIntelligenceSources) -> ClientProfile:
        raise NotImplementedError


class ClientIntelligenceManagerInterface(ABC):
    @abstractmethod
    async def build_profile(
        self,
        client_id: UUID | str,
        *,
        execution_context: dict[str, Any] | None = None,
        use_llm: bool = False,
        trace_id: str = "-",
    ) -> ClientIntelligenceResult:
        raise NotImplementedError
