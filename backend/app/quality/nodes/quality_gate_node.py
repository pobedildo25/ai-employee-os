import logging
from typing import Any
from uuid import UUID

from app.agent_runtime.state.models import AgentState
from app.quality.gate import QualityGate
from app.quality.memory_preparer import prepare_quality_memory_items
from app.quality.models import ReviewStatus

logger = logging.getLogger(__name__)

QUALITY_GATE_NODE = "quality_gate"


class QualityGateNode:
    name = QUALITY_GATE_NODE

    def __init__(self, gate: QualityGate) -> None:
        self._gate = gate

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        _log_node(state, self.name, "started")

        execution_context = state.get("execution_context") or {}
        understanding = state.get("understanding") or {}
        brand_profile = execution_context.get("brand_profile") or state.get("context", {}).get("brand_profile")

        review_context = {
            "user_goal": understanding.get("goal") or state.get("user_input", ""),
            "understanding": understanding,
            "decision": state.get("decision") or {},
            "execution_context": execution_context,
            "document_ast": state.get("document_ast"),
            "brand_profile": brand_profile,
            "render_result": state.get("render_result"),
            "document_creation_result": state.get("document_creation_result"),
            "presentation_plan": state.get("presentation_plan"),
            "strategy_result": state.get("strategy_result"),
            "client_intelligence_result": state.get("client_intelligence_result"),
            "response_message": (state.get("decision") or {}).get("response_message"),
            "revision_count": int(state.get("revision_count") or 0),
            "user_feedback": (state.get("metadata") or {}).get("user_feedback"),
        }

        review_result, revision_request = await self._gate.evaluate(
            review_context,
            trace_id=state.get("trace_id", "-"),
        )
        review_result = _merge_presentation_quality(review_result, review_context)
        review_result = _merge_strategy_quality(review_result, review_context)
        review_result = _merge_client_intelligence_quality(review_result, review_context)


        client_id = _to_uuid(execution_context.get("client_id") or state.get("context", {}).get("client_id"))
        project_id = _to_uuid(execution_context.get("project_id") or state.get("context", {}).get("project_id"))
        memory_items = prepare_quality_memory_items(
            review_result,
            user_goal=str(review_context["user_goal"]),
            client_id=client_id,
            project_id=project_id,
            session_id=state.get("metadata", {}).get("session_id"),
        )

        quality_check = {
            "passed": review_result.status == ReviewStatus.PASS,
            "score": review_result.score,
            "notes": review_result.summary,
            "issues": [issue.model_dump() for issue in review_result.issues],
            "status": review_result.status.value,
        }

        from app.revision.policies.revision_policy import can_auto_revise

        revision_count = int(state.get("revision_count") or 0)
        waiting_user = (
            review_result.status == ReviewStatus.REVISE and not can_auto_revise(revision_count)
        )

        update = {
            "current_step": self.name,
            "review_result": review_result.model_dump(mode="json"),
            "revision_request": revision_request.model_dump(mode="json") if revision_request else None,
            "quality_check": quality_check,
            "revision_count": revision_count,
            "status": "waiting_user_revision" if waiting_user else "completed",
            "result": {
                "execution_context": state.get("execution_context"),
                "understanding": state.get("understanding"),
                "decision": state.get("decision"),
                "required_capabilities": state.get("required_capabilities"),
                "task_plan": state.get("task_plan"),
                "task_execution": state.get("task_execution"),
                "document_creation_result": state.get("document_creation_result"),
                "document_ast": state.get("document_ast"),
                "render_result": state.get("render_result"),
                "review_result": review_result.model_dump(mode="json"),
                "revision_request": revision_request.model_dump(mode="json") if revision_request else None,
                "revision_result": state.get("revision_result"),
                "revision_count": revision_count,
                "quality_check": quality_check,
                "memory_candidates": [item.model_dump(mode="json") for item in memory_items],
                "processed": True,
            },
        }
        _log_node({**state, **update}, self.name, "completed")
        return update


def _log_node(state: AgentState, node_name: str, status: str) -> None:
    logger.info(
        "graph node execution | execution_id=%s trace_id=%s node_name=%s status=%s",
        state.get("execution_id", "-"),
        state.get("trace_id", "-"),
        node_name,
        status,
    )


def _merge_presentation_quality(review_result, review_context: dict[str, Any]):
    """Attach presentation checks without changing QualityGate core."""
    plan_data = review_context.get("presentation_plan")
    if not plan_data:
        return review_result

    from app.presentation_design.models import PresentationPlan
    from app.presentation_design.validators.presentation_validator import PresentationValidator
    from app.quality.models import IssueSeverity, ReviewStatus

    plan = PresentationPlan.model_validate(plan_data)
    extra = PresentationValidator().quality_issues(
        plan=plan,
        document_ast=review_context.get("document_ast"),
        brand_profile=review_context.get("brand_profile")
        if isinstance(review_context.get("brand_profile"), dict)
        else (
            review_context.get("brand_profile").model_dump(mode="json")
            if review_context.get("brand_profile") is not None
            and hasattr(review_context.get("brand_profile"), "model_dump")
            else None
        ),
    )
    if not extra:
        return review_result

    merged_issues = list(review_result.issues) + extra
    status = review_result.status
    if any(issue.severity == IssueSeverity.CRITICAL for issue in extra):
        status = ReviewStatus.ESCALATE
    elif any(issue.severity == IssueSeverity.MAJOR for issue in extra) and status == ReviewStatus.PASS:
        status = ReviewStatus.REVISE
    return review_result.model_copy(update={"issues": merged_issues, "status": status})


def _merge_strategy_quality(review_result, review_context: dict[str, Any]):
    """Attach strategy checks without changing QualityGate core."""
    result_data = review_context.get("strategy_result")
    if not result_data:
        return review_result

    from app.strategy.models import StrategyResult
    from app.strategy.validators.strategy_validator import StrategyValidator
    from app.quality.models import IssueSeverity, ReviewStatus

    result = StrategyResult.model_validate(result_data)
    extra = StrategyValidator().quality_issues(
        result=result,
        document_ast=review_context.get("document_ast") or result.document_ast,
    )
    if not extra:
        return review_result

    merged_issues = list(review_result.issues) + extra
    status = review_result.status
    if any(issue.severity == IssueSeverity.CRITICAL for issue in extra):
        status = ReviewStatus.ESCALATE
    elif any(issue.severity == IssueSeverity.MAJOR for issue in extra) and status == ReviewStatus.PASS:
        status = ReviewStatus.REVISE
    return review_result.model_copy(update={"issues": merged_issues, "status": status})


def _merge_client_intelligence_quality(review_result, review_context: dict[str, Any]):
    """Attach client intelligence checks without changing QualityGate core."""
    result_data = review_context.get("client_intelligence_result")
    profile_data = None
    if isinstance(result_data, dict):
        profile_data = result_data.get("profile")
    if profile_data is None:
        profile_data = (review_context.get("execution_context") or {}).get(
            "client_intelligence_context"
        )
    if not profile_data:
        return review_result

    from app.client_intelligence.models import ClientProfile
    from app.client_intelligence.validators.profile_validator import ProfileValidator
    from app.quality.models import IssueSeverity, ReviewStatus

    profile = ClientProfile.model_validate(profile_data)
    extra = ProfileValidator().quality_issues(profile)
    if not extra:
        return review_result

    merged_issues = list(review_result.issues) + extra
    status = review_result.status
    if any(issue.severity == IssueSeverity.CRITICAL for issue in extra):
        status = ReviewStatus.ESCALATE
    elif any(issue.severity == IssueSeverity.MAJOR for issue in extra) and status == ReviewStatus.PASS:
        status = ReviewStatus.REVISE
    return review_result.model_copy(update={"issues": merged_issues, "status": status})


def _to_uuid(value: object | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
