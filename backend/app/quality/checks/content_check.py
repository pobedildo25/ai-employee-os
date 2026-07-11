from typing import Any

from app.quality.models import IssueSeverity, QualityIssue


class ContentCheck:
    """Universal check: result exists and aligns with stated goal."""

    def run(self, *, user_goal: str, context: dict[str, Any]) -> list[QualityIssue]:
        issues: list[QualityIssue] = []
        if not user_goal.strip():
            issues.append(
                QualityIssue(
                    category="content",
                    description="User goal is missing",
                    severity=IssueSeverity.MAJOR,
                    location="user_goal",
                )
            )

        task_execution = context.get("task_execution") or {}
        execution_completed = task_execution.get("status") == "COMPLETED"
        execution_waiting_approval = task_execution.get("status") == "WAITING_APPROVAL"
        task_plan = context.get("task_plan")

        has_output = bool(
            context.get("render_result")
            or context.get("document_ast")
            or context.get("response_message")
            or (context.get("decision") or {}).get("response_message")
            or execution_completed
            or execution_waiting_approval
            or (isinstance(task_plan, dict) and task_plan.get("steps"))
        )
        decision_action = (context.get("decision") or {}).get("action")
        if decision_action in {"EXECUTE", "CREATE_PLAN"} and not has_output:
            issues.append(
                QualityIssue(
                    category="content",
                    description="Expected output artifact or document structure is missing",
                    severity=IssueSeverity.MAJOR,
                    location="artifact",
                )
            )
        return issues
