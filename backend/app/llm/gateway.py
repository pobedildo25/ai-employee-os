import logging
import time
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import trace_id_var
from app.llm.exceptions import LLMProviderError
from app.llm.interfaces.provider import LLMProvider
from app.llm.models import LLMMessage, LLMRequest, LLMResponse
from app.llm.providers.openrouter import OpenRouterProvider

logger = logging.getLogger(__name__)


class LLMGateway:
    """Single entry point for all LLM interactions."""

    def __init__(self, provider: LLMProvider, settings: Settings | None = None) -> None:
        self._provider = provider
        self._settings = settings or get_settings()

    async def chat(self, request: LLMRequest) -> LLMResponse:
        primary_model = request.model or self._settings.default_llm_model
        models = _build_model_chain(
            primary_model,
            self._settings.fallback_llm_model,
            self._settings.secondary_fallback_llm_model,
        )

        last_error: LLMProviderError | None = None
        for index, model in enumerate(models):
            try:
                return await self._invoke(
                    request,
                    model,
                    used_fallback=index > 0,
                    model_failed=models[index - 1] if index > 0 else None,
                )
            except LLMProviderError as exc:
                last_error = exc
                if index < len(models) - 1:
                    trace_id = trace_id_var.get()
                    logger.warning(
                        "model failed, trying fallback | model_failed=%s fallback_model=%s trace_id=%s error=%s",
                        model,
                        models[index + 1],
                        trace_id,
                        str(exc),
                    )
        if last_error is not None:
            raise last_error
        raise LLMProviderError("No LLM models configured")

    async def complete(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LLMResponse:
        request = LLMRequest(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            metadata=metadata or {},
        )
        return await self.chat(request)

    async def embed(
        self,
        texts: str | list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Return embedding vectors for one or more texts."""
        from app.llm.models import EmbeddingRequest

        request = EmbeddingRequest(
            input=texts,
            model=model or getattr(self._settings, "embedding_model", None),
        )
        response = await self._provider.embeddings(request)
        return response.embeddings

    async def _invoke(
        self,
        request: LLMRequest,
        model: str,
        *,
        used_fallback: bool,
        model_failed: str | None = None,
    ) -> LLMResponse:
        trace_id = trace_id_var.get()
        started = time.perf_counter()
        log_extra = {
            "trace_id": trace_id,
            "model": model,
            "used_fallback": used_fallback,
            "model_failed": model_failed,
            "fallback_model": model if used_fallback else None,
        }

        invocation_request = request.model_copy(update={"model": model})

        logger.info(
            "LLM request started | trace_id=%s model=%s messages=%d",
            trace_id,
            model,
            len(request.messages),
        )

        try:
            response = await self._provider.chat(invocation_request)
            latency_ms = response.latency_ms or (time.perf_counter() - started) * 1000
            logger.info(
                "LLM request succeeded | trace_id=%s model=%s latency_ms=%.2f "
                "prompt_tokens=%d completion_tokens=%d total_tokens=%d",
                trace_id,
                response.model,
                latency_ms,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                response.usage.total_tokens,
            )
            response.metadata = {
                **request.metadata,
                **response.metadata,
                "trace_id": trace_id,
                "used_fallback": used_fallback,
                "model_failed": model_failed,
                "fallback_model": model if used_fallback else None,
            }
            return response
        except LLMProviderError as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            logger.error(
                "LLM request failed | trace_id=%s model=%s latency_ms=%.2f error=%s",
                trace_id,
                model,
                latency_ms,
                str(exc),
                extra=log_extra,
            )
            raise
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            logger.error(
                "LLM request failed | trace_id=%s model=%s latency_ms=%.2f error=%s",
                trace_id,
                model,
                latency_ms,
                str(exc),
                extra=log_extra,
            )
            raise LLMProviderError(str(exc)) from exc


def _build_model_chain(primary: str, *fallbacks: str | None) -> list[str]:
    chain: list[str] = []
    for model in (primary, *fallbacks):
        if model and model not in chain:
            chain.append(model)
    return chain


def create_llm_gateway(settings: Settings | None = None) -> LLMGateway:
    settings = settings or get_settings()
    provider = OpenRouterProvider(settings)
    return LLMGateway(provider, settings)
