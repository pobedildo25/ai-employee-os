from typing import Any
from uuid import UUID

from app.quality.models import IssueSeverity, QualityIssue
from app.revision.models import RevisionRequest


def parse_user_feedback(feedback: str | None) -> list[str]:
    """Parse free-form user feedback into suggested change hints — no fixed commands."""
    if not feedback or not feedback.strip():
        return []

    text = feedback.strip()
    suggestions: list[str] = [text]

    lowered = text.lower()
    if any(token in lowered for token in ("меньше", "короче", "shorter", "less text", "brief")):
        suggestions.append("Reduce text volume and keep content concise")
    if any(token in lowered for token in ("больше", "детал", "more detail", "expand", "подробн")):
        suggestions.append("Add more detail to incomplete sections")
    if any(token in lowered for token in ("визуал", "visual", "image", "таблиц", "table")):
        suggestions.append("Increase visual or tabular elements where appropriate")

    seen: set[str] = set()
    unique: list[str] = []
    for item in suggestions:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def build_revision_request_from_review(
    *,
    issues: list[QualityIssue] | list[dict[str, Any]],
    suggested_changes: list[str] | None = None,
    source_artifact_id: UUID | str | None = None,
    user_feedback: str | None = None,
    revision_count: int = 0,
    metadata: dict[str, Any] | None = None,
) -> RevisionRequest:
    normalized_issues: list[QualityIssue] = []
    for issue in issues:
        if isinstance(issue, QualityIssue):
            normalized_issues.append(issue)
        else:
            severity_raw = str(issue.get("severity", IssueSeverity.MINOR.value)).lower()
            try:
                severity = IssueSeverity(severity_raw)
            except ValueError:
                severity = IssueSeverity.MINOR
            normalized_issues.append(
                QualityIssue(
                    category=str(issue.get("category", "general")),
                    description=str(issue.get("description", "")),
                    severity=severity,
                    location=issue.get("location"),
                )
            )

    feedback_suggestions = parse_user_feedback(user_feedback)
    changes = list(suggested_changes or []) + feedback_suggestions

    return RevisionRequest(
        source_artifact_id=source_artifact_id,
        issues=normalized_issues,
        suggested_changes=changes,
        user_feedback=user_feedback,
        revision_count=revision_count,
        metadata=metadata or {},
    )
