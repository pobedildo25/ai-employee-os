import logging

from app.agent_runtime.state.models import AgentState
from app.agents.decision.models import AgentDecision, DecisionType
from app.agents.executive.models import AgentUnderstanding, ExecutiveAgentResult
from app.agents.executive.prompt import build_user_message, get_executive_system_prompt
from app.agents.parsers.response_parser import ResponseParseError, parse_executive_response
from app.core.config import get_settings
from app.llm.exceptions import LLMProviderError
from app.llm.gateway import LLMGateway
from app.llm.models import LLMMessage
from app.skills.registry import CapabilityRegistry

logger = logging.getLogger(__name__)


class ExecutiveAgentError(Exception):
    """Raised when executive agent analysis fails."""


class ExecutiveAgent:
    """Understands user intent and produces structured decisions via LLM Gateway."""

    DEFAULT_MAX_RETRIES = 3

    def __init__(
        self,
        llm_gateway: LLMGateway,
        capability_registry: CapabilityRegistry | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        *,
        research_enabled: bool | None = None,
    ) -> None:
        self._gateway = llm_gateway
        self._capability_registry = capability_registry
        self._max_retries = max_retries
        if research_enabled is None:
            research_enabled = get_settings().research_enabled
        self._research_enabled = research_enabled

    async def analyze(self, state: AgentState) -> ExecutiveAgentResult:
        user_input = state.get("user_input", "")
        execution_context = state.get("execution_context") or {}
        context = state.get("context") or execution_context or {}
        trace_id = state.get("trace_id", "-")

        available_capabilities = None
        if self._capability_registry is not None and self._capability_registry.enabled:
            available_capabilities = self._capability_registry.list_available_for_prompt()

        messages: list[LLMMessage] = [
            LLMMessage(
                role="system",
                content=get_executive_system_prompt(research_enabled=self._research_enabled),
            ),
            LLMMessage(
                role="user",
                content=build_user_message(user_input, context, available_capabilities),
            ),
        ]

        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._gateway.complete(messages, temperature=0.3)
                result = parse_executive_response(response.content)
                logger.info(
                    "executive agent analyzed | trace_id=%s goal=%s action=%s attempt=%d",
                    trace_id,
                    result.understanding.goal,
                    result.decision.action.value,
                    attempt,
                )
                return result
            except LLMProviderError as exc:
                logger.warning(
                    "executive agent llm degraded | trace_id=%s attempt=%d error=%s",
                    trace_id,
                    attempt,
                    exc,
                )
                return _degraded_respond(user_input, reason=str(exc))
            except ResponseParseError as exc:
                last_error = exc
                logger.warning(
                    "executive agent parse failed | trace_id=%s attempt=%d error=%s",
                    trace_id,
                    attempt,
                    exc,
                )
                messages.append(
                    LLMMessage(
                        role="user",
                        content=(
                            "Your previous response was not valid JSON matching the required schema. "
                            "Return ONLY valid JSON with no extra text."
                        ),
                    )
                )

        logger.warning(
            "executive agent degraded after parse retries | trace_id=%s error=%s",
            trace_id,
            last_error,
        )
        return _degraded_respond(user_input, reason=str(last_error) if last_error else "parse failed")


def _degraded_respond(user_input: str, *, reason: str) -> ExecutiveAgentResult:
    return ExecutiveAgentResult(
        understanding=AgentUnderstanding(
            goal=user_input or "user request",
            summary="LLM temporarily unavailable",
            next_action="respond",
        ),
        decision=AgentDecision(
            action=DecisionType.RESPOND,
            reasoning=f"degraded: {reason}",
            response_message=(
                "Сейчас не получается обработать запрос из‑за временной ошибки сервиса. "
                "Попробуйте ещё раз чуть позже."
            ),
        ),
    )
