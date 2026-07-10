from typing import Any

from app.quality.checks.content_check import ContentCheck
from app.quality.checks.structure_check import StructureCheck
from app.quality.checks.style_check import StyleCheck
from app.quality.models import IssueSeverity, QualityIssue, ReviewResult, ReviewStatus, RevisionRequest
from app.quality.reviewer import ReviewerAgent


class QualityGate:
    PASS_SCORE_THRESHOLD = 0.7
    ESCALATE_SCORE_THRESHOLD = 0.3

    def __init__(
        self,
        reviewer: ReviewerAgent,
        content_check: ContentCheck | None = None,
        structure_check: StructureCheck | None = None,
        style_check: StyleCheck | None = None,
    ) -> None:
        self._reviewer = reviewer
        self._content_check = content_check or ContentCheck()
        self._structure_check = structure_check or StructureCheck()
        self._style_check = style_check or StyleCheck()

    async def evaluate(self, context: dict[str, Any], *, trace_id: str = "-") -> tuple[ReviewResult, RevisionRequest | None]:
        precheck_issues = self._run_prechecks(context)
        review_context = {**context, "precheck_issues": [issue.model_dump() for issue in precheck_issues]}

        if self._is_non_document_flow(context):
            review = self._reviewer.build_non_document_review(
                summary="Non-document flow completed without artifact review",
            )
            return self._finalize(review, precheck_issues), None

        review = await self._reviewer.review(review_context, trace_id=trace_id)
        final_review = self._finalize(review, precheck_issues)
        revision = self._build_revision_request(final_review, context)
        return final_review, revision

    def _run_prechecks(self, context: dict[str, Any]) -> list[QualityIssue]:
        issues: list[QualityIssue] = []
        issues.extend(
            self._content_check.run(
                user_goal=str(context.get("user_goal") or ""),
                context=context,
            )
        )
        issues.extend(self._structure_check.run(document_ast=context.get("document_ast")))
        issues.extend(
            self._style_check.run(
                brand_profile=context.get("brand_profile"),
                render_result=context.get("render_result"),
            )
        )
        return issues

    def _finalize(self, review: ReviewResult, precheck_issues: list[QualityIssue]) -> ReviewResult:
        merged_issues = list(precheck_issues) + list(review.issues)
        status = self._decide_status(review, merged_issues)
        score = self._adjust_score(review.score, merged_issues)
        return review.model_copy(
            update={
                "status": status,
                "score": score,
                "issues": merged_issues,
            }
        )

    def _decide_status(self, review: ReviewResult, issues: list[QualityIssue]) -> ReviewStatus:
        if review.status == ReviewStatus.ESCALATE:
            return ReviewStatus.ESCALATE
        if any(issue.severity == IssueSeverity.CRITICAL for issue in issues):
            return ReviewStatus.ESCALATE
        if review.score < self.ESCALATE_SCORE_THRESHOLD:
            return ReviewStatus.ESCALATE
        if review.status == ReviewStatus.REVISE:
            return ReviewStatus.REVISE
        if any(issue.severity == IssueSeverity.MAJOR for issue in issues):
            return ReviewStatus.REVISE
        if review.score < self.PASS_SCORE_THRESHOLD:
            return ReviewStatus.REVISE
        return ReviewStatus.PASS

    def _adjust_score(self, score: float, issues: list[QualityIssue]) -> float:
        penalty = 0.0
        for issue in issues:
            if issue.severity == IssueSeverity.CRITICAL:
                penalty += 0.4
            elif issue.severity == IssueSeverity.MAJOR:
                penalty += 0.2
            elif issue.severity == IssueSeverity.MINOR:
                penalty += 0.05
        return max(0.0, min(1.0, score - penalty))

    def _build_revision_request(
        self,
        review: ReviewResult,
        context: dict[str, Any],
    ) -> RevisionRequest | None:
        if review.status != ReviewStatus.REVISE:
            return None
        source_artifact = None
        render_result = context.get("render_result") or {}
        if render_result.get("artifact_id"):
            source_artifact = render_result["artifact_id"]
        return RevisionRequest(
            issues=review.issues,
            suggested_changes=review.recommendations,
            source_artifact=source_artifact,
        )

    def _is_non_document_flow(self, context: dict[str, Any]) -> bool:
        decision_action = (context.get("decision") or {}).get("action")
        return decision_action in {"RESPOND", "ASK_CLARIFICATION"}
