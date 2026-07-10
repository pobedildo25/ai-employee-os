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
        fallback_model = self._settings.fallback_llm_model

        try:
            return await self._invoke(request, primary_model, used_fallback=False)
        except LLMProviderError as primary_error:
            if not fallback_model or fallback_model == primary_model:
                raise

            logger.warning(
                "Primary model failed, switching to fallback | model=%s fallback=%s error=%s",
                primary_model,
                fallback_model,
                str(primary_error),
            )
            fallback_request = request.model_copy(update={"model": fallback_model})
            return await self._invoke(fallback_request, fallback_model, used_fallback=True)

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

    async def _invoke(self, request: LLMRequest, model: str, used_fallback: bool) -> LLMResponse:
        trace_id = trace_id_var.get()
        started = time.perf_counter()
        log_extra = {
            "trace_id": trace_id,
            "model": model,
            "used_fallback": used_fallback,
        }

        invocation_request = request if request.model else request.model_copy(update={"model": model})

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
            }
            return response
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
            raise


def create_llm_gateway(settings: Settings | None = None) -> LLMGateway:
    settings = settings or get_settings()
    provider = OpenRouterProvider(settings)
    return LLMGateway(provider, settings)
