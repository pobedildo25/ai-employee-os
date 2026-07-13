import asyncio
import logging
import time
from collections.abc import AsyncIterator

import httpx

from app.core.config import Settings
from app.llm.exceptions import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
)
from app.llm.interfaces.provider import LLMProvider
from app.llm.models import EmbeddingRequest, EmbeddingResponse, LLMRequest, LLMResponse, TokenUsage

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class OpenRouterProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        if not settings.openrouter_api_key or settings.openrouter_api_key == "change-me":
            logger.warning("OpenRouter API key is not configured")

    async def chat(self, request: LLMRequest) -> LLMResponse:
        if not self._settings.openrouter_api_key:
            raise LLMConfigurationError("OPENROUTER_API_KEY is not set")

        model = request.model or self._settings.default_llm_model
        payload: dict[str, object] = {
            "model": model,
            "messages": [message.model_dump() for message in request.messages],
            "temperature": request.temperature,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        headers = {
            "Authorization": f"Bearer {self._settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self._settings.openrouter_base_url.rstrip('/')}/chat/completions"
        started = time.perf_counter()
        last_error: Exception | None = None

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(url, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                last_error = LLMProviderError(f"OpenRouter request failed: {exc}")
                if attempt >= _MAX_ATTEMPTS:
                    raise last_error from exc
                await self._backoff(attempt)
                continue

            if response.status_code == 401:
                raise LLMAuthenticationError("OpenRouter authentication failed")

            if response.status_code in _RETRYABLE_STATUS:
                if response.status_code == 429:
                    last_error = LLMRateLimitError("OpenRouter rate limit exceeded")
                else:
                    last_error = LLMProviderError(
                        f"OpenRouter error {response.status_code}: {response.text[:500]}"
                    )
                if attempt >= _MAX_ATTEMPTS:
                    raise last_error
                logger.warning(
                    "openrouter retryable status | status=%s attempt=%d/%d",
                    response.status_code,
                    attempt,
                    _MAX_ATTEMPTS,
                )
                await self._backoff(attempt)
                continue

            if response.status_code >= 400:
                raise LLMProviderError(
                    f"OpenRouter error {response.status_code}: {response.text[:500]}"
                )

            latency_ms = (time.perf_counter() - started) * 1000
            data = response.json()
            try:
                content = data["choices"][0]["message"]["content"]
                response_model = data.get("model", model)
                usage_data = data.get("usage", {})
                usage = TokenUsage(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0),
                )
            except (KeyError, IndexError, TypeError) as exc:
                raise LLMProviderError(f"Unexpected OpenRouter response format: {exc}") from exc

            return LLMResponse(
                content=content,
                model=response_model,
                usage=usage,
                latency_ms=latency_ms,
                metadata={"provider": "openrouter", "attempts": attempt},
            )

        raise last_error or LLMProviderError("OpenRouter request failed after retries")

    async def _backoff(self, attempt: int) -> None:
        delay = min(2 ** (attempt - 1), 8)
        await asyncio.sleep(delay)

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        raise NotImplementedError("Streaming is not implemented yet")

        yield ""  # pragma: no cover

    async def embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        raise NotImplementedError("Embeddings are not implemented yet")
