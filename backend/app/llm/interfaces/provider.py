from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.llm.models import EmbeddingRequest, EmbeddingResponse, LLMRequest, LLMResponse


class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, request: LLMRequest) -> LLMResponse:
        ...

    @abstractmethod
    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        ...

    @abstractmethod
    async def embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        ...
