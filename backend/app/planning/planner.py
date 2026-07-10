import logging

from app.agents.executive.models import AgentUnderstanding
from app.agents.parsers.response_parser import ResponseParseError
from app.context.models import ExecutionContext
from app.llm.gateway import LLMGateway
from app.llm.models import LLMMessage
from app.planning.interfaces.planner import TaskPlannerInterface
from app.planning.models import PlanStatus, TaskPlan
from app.planning.parsers.plan_parser import parse_task_plan
from app.planning.prompt import PLANNER_SYSTEM_PROMPT, build_planner_user_message
from app.skills.models import Capability

logger = logging.getLogger(__name__)


class TaskPlannerError(Exception):
    """Raised when task planning fails."""


class TaskPlanner(TaskPlannerInterface):
    DEFAULT_MAX_RETRIES = 3

    def __init__(self, llm_gateway: LLMGateway, max_retries: int = DEFAULT_MAX_RETRIES) -> None:
        self._gateway = llm_gateway
        self._max_retries = max_retries

    async def create_plan(
        self,
        *,
        understanding: AgentUnderstanding,
        execution_context: ExecutionContext | dict,
        available_capabilities: list[Capability],
        trace_id: str = "-",
    ) -> TaskPlan:
        context_dict = (
            execution_context.model_dump()
            if isinstance(execution_context, ExecutionContext)
            else execution_context
        )
        capability_prompt = [
            {"name": capability.name, "description": capability.description}
            for capability in available_capabilities
        ]

        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=PLANNER_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=build_planner_user_message(
                    understanding.model_dump(),
                    context_dict,
                    capability_prompt,
                ),
            ),
        ]

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._gateway.complete(messages, temperature=0.3)
                plan = parse_task_plan(response.content)
                plan.status = PlanStatus.READY
                logger.info(
                    "task plan created | trace_id=%s steps=%d attempt=%d",
                    trace_id,
                    len(plan.steps),
                    attempt,
                )
                return plan
            except ResponseParseError as exc:
                last_error = exc
                logger.warning(
                    "task plan parse failed | trace_id=%s attempt=%d error=%s",
                    trace_id,
                    attempt,
                    exc,
                )
                messages.append(
                    LLMMessage(
                        role="user",
                        content="Return ONLY valid JSON matching the required plan schema.",
                    )
                )

        raise TaskPlannerError(
            f"Failed to create valid task plan after {self._max_retries} attempts: {last_error}"
        )
