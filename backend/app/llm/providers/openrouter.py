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
from app.llm.models import (
    EmbeddingRequest,
    EmbeddingResponse,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    TokenUsage,
)

logger = logging.getLogger(__name__)


def _serialize_message(message: LLMMessage) -> dict[str, object]:
    """Serialize a message for the OpenRouter chat API.

    Multimodal messages carry ``content_parts`` (text + image_url); plain
    messages carry a string ``content``.
    """
    if message.content_parts is not None:
        return {"role": message.role, "content": message.content_parts}
    return {"role": message.role, "content": message.content}


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
            "messages": [_serialize_message(message) for message in request.messages],
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

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"OpenRouter request failed: {exc}") from exc

        latency_ms = (time.perf_counter() - started) * 1000

        if response.status_code == 401:
            raise LLMAuthenticationError("OpenRouter authentication failed")
        if response.status_code == 429:
            raise LLMRateLimitError("OpenRouter rate limit exceeded")
        if response.status_code >= 400:
            raise LLMProviderError(
                f"OpenRouter error {response.status_code}: {response.text[:500]}"
            )

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
            metadata={"provider": "openrouter"},
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        raise NotImplementedError("Streaming is not implemented yet")

        yield ""  # pragma: no cover

    async def embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        if not self._settings.openrouter_api_key:
            raise LLMConfigurationError("OPENROUTER_API_KEY is not set")

        model = request.model or getattr(self._settings, "embedding_model", "")
        if not model:
            raise LLMConfigurationError("Embedding model is not configured")

        payload = {"model": model, "input": request.input}
        headers = {
            "Authorization": f"Bearer {self._settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._settings.openrouter_base_url.rstrip('/')}/embeddings"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"OpenRouter embeddings request failed: {exc}") from exc

        if response.status_code == 401:
            raise LLMAuthenticationError("OpenRouter authentication failed")
        if response.status_code == 429:
            raise LLMRateLimitError("OpenRouter rate limit exceeded")
        if response.status_code >= 400:
            raise LLMProviderError(
                f"OpenRouter embeddings error {response.status_code}: {response.text[:500]}"
            )

        data = response.json()
        try:
            rows = sorted(data["data"], key=lambda row: row.get("index", 0))
            embeddings = [row["embedding"] for row in rows]
            usage_data = data.get("usage", {})
            usage = TokenUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(f"Unexpected OpenRouter embeddings format: {exc}") from exc

        return EmbeddingResponse(embeddings=embeddings, model=data.get("model", model), usage=usage)
