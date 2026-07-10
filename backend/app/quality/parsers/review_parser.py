import json
from typing import Any

from app.agents.parsers.response_parser import ResponseParseError, extract_json_content
from app.quality.models import IssueSeverity, QualityIssue, ReviewResult, ReviewStatus


def parse_review_response(raw: str) -> ReviewResult:
    content = extract_json_content(raw)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ResponseParseError(f"Invalid JSON: {exc}") from exc

    issues: list[QualityIssue] = []
    for item in data.get("issues") or []:
        if not isinstance(item, dict):
            continue
        severity_raw = str(item.get("severity", IssueSeverity.MINOR.value)).lower()
        try:
            severity = IssueSeverity(severity_raw)
        except ValueError:
            severity = IssueSeverity.MINOR
        issues.append(
            QualityIssue(
                category=str(item.get("category", "general")),
                description=str(item.get("description", "")),
                severity=severity,
                location=item.get("location"),
            )
        )

    status_raw = str(data.get("status", ReviewStatus.PASS.value)).upper()
    try:
        status = ReviewStatus(status_raw)
    except ValueError:
        status = ReviewStatus.REVISE

    score = float(data.get("score", 0.5))
    score = max(0.0, min(1.0, score))

    return ReviewResult(
        status=status,
        score=score,
        summary=str(data.get("summary", "")),
        issues=issues,
        recommendations=[str(item) for item in data.get("recommendations") or []],
        metadata=dict(data.get("metadata") or {}),
    )
