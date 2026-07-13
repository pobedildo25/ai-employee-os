import json
import logging
from typing import Any

from app.agents.parsers.response_parser import ResponseParseError, extract_json_content
from app.learning.models import ExtractedRuleCandidate, LearningScope, LearningSignal, RuleExtractionResult
from app.learning.prompts.rule_extraction import (
    RULE_EXTRACTION_SYSTEM_PROMPT,
    build_rule_extraction_message,
)
from app.llm.exceptions import LLMProviderError
from app.llm.gateway import LLMGateway
from app.llm.models import LLMMessage

logger = logging.getLogger(__name__)


class LearningExtractorError(Exception):
    pass


class LearningExtractor:
    DEFAULT_MAX_RETRIES = 3

    def __init__(self, llm_gateway: LLMGateway, max_retries: int = DEFAULT_MAX_RETRIES) -> None:
        self._gateway = llm_gateway
        self._max_retries = max_retries

    async def extract(
        self,
        signal: LearningSignal,
        *,
        context: dict[str, Any] | None = None,
        trace_id: str = "-",
    ) -> RuleExtractionResult:
        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=RULE_EXTRACTION_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=build_rule_extraction_message(
                    feedback=signal.text,
                    source=signal.source.value,
                    context=context,
                ),
            ),
        ]
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._gateway.complete(messages, temperature=0.1)
                result = parse_rule_extraction_response(response.content)
                logger.info(
                    "learning extracted | trace_id=%s should_learn=%s attempt=%d",
                    trace_id,
                    result.should_learn,
                    attempt,
                )
                return result
            except LLMProviderError as exc:
                logger.warning(
                    "learning extract degraded | trace_id=%s attempt=%d error=%s",
                    trace_id,
                    attempt,
                    exc,
                )
                return RuleExtractionResult(
                    rule=None,
                    confidence=0.0,
                    should_learn=False,
                    reason=f"llm unavailable: {exc}",
                )
            except (ResponseParseError, ValueError) as exc:
                last_error = exc
                messages.append(
                    LLMMessage(
                        role="user",
                        content="Return ONLY valid JSON matching the required learning schema.",
                    )
                )
        logger.warning(
            "learning extract degraded after retries | trace_id=%s error=%s",
            trace_id,
            last_error,
        )
        return RuleExtractionResult(
            rule=None,
            confidence=0.0,
            should_learn=False,
            reason=f"parse failed after {self._max_retries} attempts: {last_error}",
        )


def parse_rule_extraction_response(raw: str) -> RuleExtractionResult:
    content = extract_json_content(raw)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ResponseParseError(f"Invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ResponseParseError("Learning response must be an object")

    should_learn = bool(data.get("should_learn", False))
    confidence = float(data.get("confidence", 0.0))
    confidence = max(0.0, min(1.0, confidence))
    reason = data.get("reason")
    rule_raw = data.get("rule")
    rule: ExtractedRuleCandidate | None = None
    if isinstance(rule_raw, dict):
        category = str(rule_raw.get("category") or "").strip()
        key = str(rule_raw.get("key") or "").strip()
        value = str(rule_raw.get("value") or "").strip()
        if category and key and value:
            rule_confidence = float(rule_raw.get("confidence", confidence))
            scope_raw = str(rule_raw.get("scope") or LearningScope.CLIENT.value)
            try:
                scope = LearningScope(scope_raw)
            except ValueError:
                scope = LearningScope.CLIENT
            rule = ExtractedRuleCandidate(
                category=category,
                key=key,
                value=value,
                confidence=max(0.0, min(1.0, rule_confidence)),
                scope=scope,
            )
            confidence = max(confidence, rule.confidence)

    if rule is None:
        should_learn = False

    return RuleExtractionResult(
        rule=rule,
        confidence=confidence,
        should_learn=should_learn,
        reason=str(reason) if reason else None,
    )
