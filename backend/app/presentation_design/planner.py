import json
import logging
from typing import Any

from app.agents.parsers.response_parser import ResponseParseError, extract_json_content
from app.llm.exceptions import LLMProviderError
from app.llm.gateway import LLMGateway
from app.llm.models import LLMMessage
from app.presentation_design.interfaces.designer import PresentationPlannerInterface
from app.presentation_design.models import (
    ContentBlock,
    PresentationPlan,
    PresentationType,
    SlidePlan,
    SlideType,
)
from app.presentation_design.prompt import PRESENTATION_PLANNER_SYSTEM_PROMPT, build_planner_user_message

logger = logging.getLogger(__name__)


class PresentationPlanner(PresentationPlannerInterface):
    DEFAULT_MAX_RETRIES = 3

    def __init__(self, llm_gateway: LLMGateway, max_retries: int = DEFAULT_MAX_RETRIES) -> None:
        self._gateway = llm_gateway
        self._max_retries = max_retries

    async def plan(
        self,
        *,
        goal: str,
        context: dict[str, Any] | None = None,
        brand_profile: dict[str, Any] | None = None,
        learning_rules: list[dict[str, Any]] | None = None,
        presentation_type: str | None = None,
        trace_id: str = "-",
    ) -> PresentationPlan:
        messages = [
            LLMMessage(role="system", content=PRESENTATION_PLANNER_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=build_planner_user_message(
                    goal=goal,
                    context=context or {},
                    brand_profile=brand_profile,
                    learning_rules=learning_rules,
                    presentation_type=presentation_type,
                ),
            ),
        ]
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._gateway.complete(messages, temperature=0.3)
                plan = parse_presentation_plan(response.content)
                logger.info(
                    "presentation planned | trace_id=%s slides=%d attempt=%d",
                    trace_id,
                    len(plan.slides),
                    attempt,
                )
                return plan
            except LLMProviderError as exc:
                logger.warning(
                    "presentation llm degraded | trace_id=%s attempt=%d error=%s",
                    trace_id,
                    attempt,
                    exc,
                )
                return PresentationPlan(
                    title="Presentation unavailable",
                    goal=goal,
                    slides=[],
                    metadata={"status": "failed", "degraded": True, "error": str(exc)},
                )
            except (ResponseParseError, ValueError) as exc:
                last_error = exc
                messages.append(
                    LLMMessage(
                        role="user",
                        content="Return ONLY valid JSON for PresentationPlan schema.",
                    )
                )
        logger.warning(
            "presentation degraded after parse retries | trace_id=%s error=%s",
            trace_id,
            last_error,
        )
        return PresentationPlan(
            title="Presentation unavailable",
            goal=goal,
            slides=[],
            metadata={
                "status": "failed",
                "degraded": True,
                "error": str(last_error) if last_error else "parse failed",
            },
        )


def parse_presentation_plan(raw: str) -> PresentationPlan:
    content = extract_json_content(raw)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ResponseParseError(f"Invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ResponseParseError("Presentation plan must be an object")

    slides_raw = data.get("slides") or []
    slides: list[SlidePlan] = []
    for index, item in enumerate(slides_raw):
        if not isinstance(item, dict):
            continue
        slide_type_raw = str(item.get("slide_type") or item.get("type") or "FEATURES").upper()
        try:
            slide_type = SlideType(slide_type_raw)
        except ValueError:
            slide_type = SlideType.FEATURES
        blocks = []
        for block in item.get("content_blocks") or []:
            if isinstance(block, dict) and block.get("text"):
                blocks.append(
                    ContentBlock(kind=str(block.get("kind") or "paragraph"), text=str(block["text"]))
                )
            elif isinstance(block, str) and block.strip():
                blocks.append(ContentBlock(text=block.strip()))
        if not blocks and item.get("title"):
            blocks.append(ContentBlock(text=str(item.get("purpose") or item["title"])))
        slides.append(
            SlidePlan(
                order=int(item.get("order", index)),
                slide_type=slide_type,
                title=str(item.get("title") or f"Slide {index + 1}"),
                purpose=str(item.get("purpose") or ""),
                content_blocks=blocks,
                visual_notes=item.get("visual_notes"),
            )
        )
    slides.sort(key=lambda slide: slide.order)

    type_raw = str(data.get("presentation_type") or data.get("type") or "custom").lower()
    try:
        presentation_type = PresentationType(type_raw)
    except ValueError:
        presentation_type = PresentationType.CUSTOM

    return PresentationPlan(
        title=str(data.get("title") or "Presentation"),
        goal=str(data.get("goal") or ""),
        audience=data.get("audience"),
        presentation_type=presentation_type,
        slides=slides,
        brand_profile_id=data.get("brand_profile_id"),
        metadata=dict(data.get("metadata") or {}),
    )
