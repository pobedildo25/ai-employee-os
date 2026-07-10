from collections.abc import AsyncIterator

import pytest

from app.core.config import Settings
from app.llm.exceptions import LLMProviderError
from app.llm.gateway import LLMGateway, create_llm_gateway
from app.llm.interfaces.provider import LLMProvider
from app.llm.models import EmbeddingRequest, EmbeddingResponse, LLMMessage, LLMRequest, LLMResponse, TokenUsage
from app.llm.token_counter import count_tokens


class MockProvider(LLMProvider):
    def __init__(self, responses: list[LLMResponse] | None = None, errors: list[Exception] | None = None) -> None:
        self._responses = list(responses or [])
        self._errors = list(errors or [])
        self.calls: list[LLMRequest] = []

    async def chat(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        if self._errors:
            raise self._errors.pop(0)
        if self._responses:
            return self._responses.pop(0)
        return LLMResponse(content="mock response", model=request.model or "mock-model")

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        raise NotImplementedError

        yield ""  # pragma: no cover

    async def embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        raise NotImplementedError


@pytest.fixture
def settings() -> Settings:
    return Settings(
        openrouter_api_key="test-key",
        openrouter_base_url="https://openrouter.ai/api/v1",
        default_llm_model="primary-model",
        fallback_llm_model="fallback-model",
    )


def test_create_llm_gateway(settings: Settings) -> None:
    gateway = create_llm_gateway(settings)
    assert isinstance(gateway, LLMGateway)


@pytest.mark.asyncio
async def test_gateway_chat_success(settings: Settings) -> None:
    provider = MockProvider(
        responses=[
            LLMResponse(
                content="Hello!",
                model="primary-model",
                usage=TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
                latency_ms=50.0,
            )
        ]
    )
    gateway = LLMGateway(provider, settings)

    response = await gateway.chat(
        LLMRequest(messages=[LLMMessage(role="user", content="Hi")])
    )

    assert response.content == "Hello!"
    assert response.model == "primary-model"
    assert provider.calls[0].model == "primary-model"


@pytest.mark.asyncio
async def test_gateway_complete_helper(settings: Settings) -> None:
    provider = MockProvider()
    gateway = LLMGateway(provider, settings)

    response = await gateway.complete(
        messages=[LLMMessage(role="user", content="Question")],
        temperature=0.2,
    )

    assert response.content == "mock response"
    assert provider.calls[0].temperature == 0.2


@pytest.mark.asyncio
async def test_gateway_fallback_on_primary_failure(settings: Settings) -> None:
    provider = MockProvider(
        errors=[LLMProviderError("primary failed")],
        responses=[
            LLMResponse(
                content="fallback answer",
                model="fallback-model",
                usage=TokenUsage(total_tokens=12),
            )
        ],
    )
    gateway = LLMGateway(provider, settings)

    response = await gateway.chat(
        LLMRequest(messages=[LLMMessage(role="user", content="Hi")])
    )

    assert response.content == "fallback answer"
    assert len(provider.calls) == 2
    assert provider.calls[0].model == "primary-model"
    assert provider.calls[1].model == "fallback-model"
    assert response.metadata.get("used_fallback") is True


def test_token_counter_estimate() -> None:
    assert count_tokens("hello world") >= 1
    assert count_tokens("") == 0
