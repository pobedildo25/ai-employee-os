import pytest
import httpx
import respx

from app.core.config import Settings
from app.llm.exceptions import LLMAuthenticationError, LLMProviderError
from app.llm.models import LLMMessage, LLMRequest
from app.llm.providers.openrouter import OpenRouterProvider


@pytest.fixture
def settings() -> Settings:
    return Settings(
        openrouter_api_key="test-api-key",
        openrouter_base_url="https://openrouter.ai/api/v1",
        default_llm_model="anthropic/claude-sonnet-4",
        fallback_llm_model="openai/gpt-4o-mini",
    )


@pytest.mark.asyncio
@respx.mock
async def test_openrouter_provider_chat_success(settings: Settings) -> None:
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "anthropic/claude-sonnet-4",
                "choices": [{"message": {"role": "assistant", "content": "Test response"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )
    )

    provider = OpenRouterProvider(settings)
    response = await provider.chat(
        LLMRequest(messages=[LLMMessage(role="user", content="Hello")], model="anthropic/claude-sonnet-4")
    )

    assert response.content == "Test response"
    assert response.usage.total_tokens == 15
    assert route.called
    assert route.calls[0].request.headers["Authorization"] == "Bearer test-api-key"


@pytest.mark.asyncio
@respx.mock
async def test_openrouter_provider_auth_error(settings: Settings) -> None:
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(401, json={"error": "Unauthorized"})
    )

    provider = OpenRouterProvider(settings)
    with pytest.raises(LLMAuthenticationError):
        await provider.chat(LLMRequest(messages=[LLMMessage(role="user", content="Hello")]))


@pytest.mark.asyncio
@respx.mock
async def test_openrouter_retries_on_429_then_succeeds(settings: Settings, monkeypatch) -> None:
    async def _no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr("app.llm.providers.openrouter.asyncio.sleep", _no_sleep)

    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(429, json={"error": "rate limit"}),
            httpx.Response(429, json={"error": "rate limit"}),
            httpx.Response(
                200,
                json={
                    "model": "anthropic/claude-sonnet-4",
                    "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                },
            ),
        ]
    )
    provider = OpenRouterProvider(settings)
    response = await provider.chat(LLMRequest(messages=[LLMMessage(role="user", content="Hi")]))
    assert response.content == "ok"
    assert route.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_openrouter_raises_after_retry_exhaustion(settings: Settings, monkeypatch) -> None:
    async def _no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr("app.llm.providers.openrouter.asyncio.sleep", _no_sleep)
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(503, json={"error": "unavailable"})
    )
    provider = OpenRouterProvider(settings)
    with pytest.raises(LLMProviderError):
        await provider.chat(LLMRequest(messages=[LLMMessage(role="user", content="Hi")]))
