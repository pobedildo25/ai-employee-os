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
