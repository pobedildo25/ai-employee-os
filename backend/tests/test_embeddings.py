from __future__ import annotations

import httpx
import pytest
import respx

from app.core.config import Settings
from app.llm.gateway import LLMGateway
from app.llm.models import EmbeddingRequest, EmbeddingResponse, LLMRequest, LLMResponse
from app.llm.providers.openrouter import OpenRouterProvider
from app.memory.semantic.qdrant_memory import stub_embed


class FakeProvider:
    def __init__(self, vectors: list[list[float]]) -> None:
        self._vectors = vectors
        self.requests: list[EmbeddingRequest] = []

    async def chat(self, request: LLMRequest) -> LLMResponse:  # pragma: no cover
        raise NotImplementedError

    async def stream(self, request):  # pragma: no cover
        yield ""

    async def embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        self.requests.append(request)
        return EmbeddingResponse(embeddings=self._vectors, model="fake")


def _settings() -> Settings:
    return Settings(
        openrouter_api_key="test-key",
        openrouter_base_url="https://openrouter.ai/api/v1",
        embedding_model="openai/text-embedding-3-small",
    )


@pytest.mark.asyncio
async def test_gateway_embed_delegates_to_provider() -> None:
    provider = FakeProvider([[0.1, 0.2, 0.3]])
    gateway = LLMGateway(provider, _settings())

    vectors = await gateway.embed("hello")

    assert vectors == [[0.1, 0.2, 0.3]]
    assert provider.requests[0].input == "hello"


@pytest.mark.asyncio
@respx.mock
async def test_openrouter_embeddings_parses_response() -> None:
    respx.post("https://openrouter.ai/api/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "openai/text-embedding-3-small",
                "data": [
                    {"index": 1, "embedding": [0.4, 0.5]},
                    {"index": 0, "embedding": [0.1, 0.2]},
                ],
                "usage": {"prompt_tokens": 3, "total_tokens": 3},
            },
        )
    )
    provider = OpenRouterProvider(_settings())

    response = await provider.embeddings(EmbeddingRequest(input=["a", "b"]))

    # sorted by index
    assert response.embeddings == [[0.1, 0.2], [0.4, 0.5]]


def test_stub_embed_dimensions() -> None:
    assert len(stub_embed("text", dimensions=32)) == 32
    assert stub_embed("text") == stub_embed("text")
