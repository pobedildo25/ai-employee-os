import json
import logging
from typing import Any

from app.agents.parsers.response_parser import ResponseParseError, extract_json_content
from app.llm.gateway import LLMGateway
from app.llm.models import LLMMessage
from app.strategy.frameworks import normalize_framework
from app.strategy.interfaces.strategist import StrategyPlannerInterface
from app.strategy.models import (
    StrategyInsight,
    StrategyRequest,
    StrategyResult,
    StrategySection,
    StrategyType,
)
from app.strategy.prompt import STRATEGY_PLANNER_SYSTEM_PROMPT, build_planner_user_message

logger = logging.getLogger(__name__)


class StrategyPlanner(StrategyPlannerInterface):
    DEFAULT_MAX_RETRIES = 3

    def __init__(self, llm_gateway: LLMGateway, max_retries: int = DEFAULT_MAX_RETRIES) -> None:
        self._gateway = llm_gateway
        self._max_retries = max_retries

    async def plan(self, request: StrategyRequest, *, trace_id: str = "-") -> StrategyResult:
        type_hint = request.strategy_type.value if request.strategy_type else None
        messages = [
            LLMMessage(role="system", content=STRATEGY_PLANNER_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=build_planner_user_message(
                    goal=request.goal,
                    client_context=request.client_context,
                    project_context=request.project_context,
                    audience=request.audience,
                    constraints=request.constraints,
                    learning_rules=request.learning_rules,
                    strategy_type=type_hint,
                    brand_profile=request.brand_profile,
                ),
            ),
        ]
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._gateway.complete(messages, temperature=0.3)
                result = parse_strategy_result(response.content, fallback_type=request.strategy_type)
                logger.info(
                    "strategy planned | trace_id=%s type=%s insights=%d attempt=%d",
                    trace_id,
                    result.strategy_type.value,
                    len(result.insights),
                    attempt,
                )
                return result
            except (ResponseParseError, ValueError) as exc:
                last_error = exc
                messages.append(
                    LLMMessage(
                        role="user",
                        content="Return ONLY valid JSON for StrategyResult schema.",
                    )
                )
        raise ResponseParseError(f"Failed to plan strategy: {last_error}")


def parse_strategy_result(
    raw: str,
    *,
    fallback_type: StrategyType | None = None,
) -> StrategyResult:
    content = extract_json_content(raw)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ResponseParseError(f"Invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ResponseParseError("Strategy result must be an object")

    type_raw = str(data.get("strategy_type") or data.get("type") or "").lower()
    try:
        strategy_type = StrategyType(type_raw) if type_raw else (fallback_type or StrategyType.MARKETING_STRATEGY)
    except ValueError:
        strategy_type = fallback_type or StrategyType.MARKETING_STRATEGY

    insights: list[StrategyInsight] = []
    for item in data.get("insights") or []:
        if not isinstance(item, dict):
            continue
        insights.append(
            StrategyInsight(
                category=str(item.get("category") or "general"),
                title=str(item.get("title") or "Insight"),
                description=str(item.get("description") or ""),
                confidence=float(item.get("confidence", 0.7)),
            )
        )

    recommendations = [str(r) for r in (data.get("recommendations") or []) if str(r).strip()]

    sections: list[StrategySection] = []
    for item in data.get("sections") or []:
        if not isinstance(item, dict):
            continue
        paragraphs = item.get("paragraphs") or []
        if isinstance(paragraphs, str):
            paragraphs = [paragraphs]
        sections.append(
            StrategySection(
                title=str(item.get("title") or "Section"),
                paragraphs=[str(p) for p in paragraphs if str(p).strip()],
            )
        )

    framework_raw = data.get("framework_data") if isinstance(data.get("framework_data"), dict) else {}
    if not framework_raw:
        # Accept top-level framework keys as soft input
        framework_raw = {
            k: data[k]
            for k in (
                "strengths",
                "weaknesses",
                "opportunities",
                "threats",
                "audience",
                "problem",
                "solution",
                "differentiation",
                "goals",
                "channels",
                "content",
                "metrics",
                "competitors",
                "comparison_points",
            )
            if k in data
        }

    return StrategyResult(
        strategy_type=strategy_type,
        summary=str(data.get("summary") or ""),
        insights=insights,
        recommendations=recommendations,
        sections=sections,
        framework_data=normalize_framework(strategy_type, framework_raw),
        metadata=dict(data.get("metadata") or {}),
        missing_information=[str(m) for m in (data.get("missing_information") or []) if str(m).strip()],
    )
