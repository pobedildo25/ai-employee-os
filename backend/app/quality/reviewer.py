import logging
from typing import Any

from app.agents.parsers.response_parser import ResponseParseError
from app.llm.exceptions import LLMProviderError
from app.llm.gateway import LLMGateway
from app.llm.models import LLMMessage
from app.quality.interfaces.reviewer import ReviewerInterface
from app.quality.models import IssueSeverity, QualityIssue, ReviewResult, ReviewStatus
from app.quality.parsers.review_parser import parse_review_response
from app.quality.prompt import REVIEWER_SYSTEM_PROMPT, build_reviewer_user_message

logger = logging.getLogger(__name__)


class ReviewerAgentError(Exception):
    """Raised when reviewer analysis fails."""


class ReviewerAgent(ReviewerInterface):
    DEFAULT_MAX_RETRIES = 3

    def __init__(self, llm_gateway: LLMGateway, max_retries: int = DEFAULT_MAX_RETRIES) -> None:
        self._gateway = llm_gateway
        self._max_retries = max_retries

    async def review(self, context: dict[str, Any], *, trace_id: str = "-") -> ReviewResult:
        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=REVIEWER_SYSTEM_PROMPT),
            LLMMessage(role="user", content=build_reviewer_user_message(context)),
        ]

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._gateway.complete(messages, temperature=0.2)
                result = parse_review_response(response.content)
                logger.info(
                    "reviewer completed | trace_id=%s status=%s score=%.2f attempt=%d",
                    trace_id,
                    result.status.value,
                    result.score,
                    attempt,
                )
                return result
            except LLMProviderError as exc:
                logger.warning(
                    "reviewer llm degraded | trace_id=%s attempt=%d error=%s",
                    trace_id,
                    attempt,
                    exc,
                )
                return ReviewResult(
                    status=ReviewStatus.ESCALATE,
                    score=0.0,
                    summary="Quality review skipped: LLM unavailable",
                    issues=[
                        QualityIssue(
                            category="system",
                            description=str(exc),
                            severity=IssueSeverity.CRITICAL,
                        )
                    ],
                    recommendations=["Retry the review when the LLM is available."],
                    metadata={"degraded": True, "status": "failed", "error": str(exc)},
                )
            except ResponseParseError as exc:
                last_error = exc
                logger.warning(
                    "review parse failed | trace_id=%s attempt=%d error=%s",
                    trace_id,
                    attempt,
                    exc,
                )
                messages.append(
                    LLMMessage(
                        role="user",
                        content="Return ONLY valid JSON matching the required review schema.",
                    )
                )

        logger.warning(
            "reviewer degraded after parse retries | trace_id=%s error=%s",
            trace_id,
            last_error,
        )
        return ReviewResult(
            status=ReviewStatus.ESCALATE,
            score=0.0,
            summary="Quality review skipped: invalid LLM response",
            issues=[
                QualityIssue(
                    category="system",
                    description=str(last_error) if last_error else "parse failed",
                    severity=IssueSeverity.CRITICAL,
                )
            ],
            recommendations=["Retry the review."],
            metadata={
                "degraded": True,
                "status": "failed",
                "error": str(last_error) if last_error else "parse failed",
            },
        )

    def build_non_document_review(self, *, summary: str) -> ReviewResult:
        return ReviewResult(
            status=ReviewStatus.PASS,
            score=1.0,
            summary=summary,
            issues=[],
            recommendations=[],
        )
