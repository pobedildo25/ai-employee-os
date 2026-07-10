import logging

from app.agent_runtime.state.models import AgentState
from app.agents.executive.models import ExecutiveAgentResult
from app.agents.executive.prompt import EXECUTIVE_SYSTEM_PROMPT, build_user_message
from app.agents.parsers.response_parser import ResponseParseError, parse_executive_response
from app.llm.gateway import LLMGateway
from app.llm.models import LLMMessage

logger = logging.getLogger(__name__)


class ExecutiveAgentError(Exception):
    """Raised when executive agent analysis fails."""


class ExecutiveAgent:
    """Understands user intent and produces structured decisions via LLM Gateway."""

    DEFAULT_MAX_RETRIES = 3

    def __init__(self, llm_gateway: LLMGateway, max_retries: int = DEFAULT_MAX_RETRIES) -> None:
        self._gateway = llm_gateway
        self._max_retries = max_retries

    async def analyze(self, state: AgentState) -> ExecutiveAgentResult:
        user_input = state.get("user_input", "")
        context = state.get("context") or {}
        trace_id = state.get("trace_id", "-")

        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=EXECUTIVE_SYSTEM_PROMPT),
            LLMMessage(role="user", content=build_user_message(user_input, context)),
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

        raise ExecutiveAgentError(
            f"Failed to obtain valid structured response after {self._max_retries} attempts: {last_error}"
        )
