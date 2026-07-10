from typing import Any

from app.quality.models import IssueSeverity, QualityIssue


class StyleCheck:
    """Universal check: brand profile presence and basic style metadata."""

    def run(
        self,
        *,
        brand_profile: dict[str, Any] | None,
        render_result: dict[str, Any] | None,
    ) -> list[QualityIssue]:
        if render_result is None:
            return []

        issues: list[QualityIssue] = []
        metadata = render_result.get("metadata") or {}

        if brand_profile is None:
            issues.append(
                QualityIssue(
                    category="style",
                    description="Brand profile was not provided for rendered output",
                    severity=IssueSeverity.MINOR,
                    location="brand_profile",
                )
            )
            return issues

        typography = brand_profile.get("typography") or {}
        colors = brand_profile.get("colors") or {}
        if not typography.get("body_font") and not typography.get("heading_font"):
            issues.append(
                QualityIssue(
                    category="style",
                    description="Brand profile lacks typography settings",
                    severity=IssueSeverity.MINOR,
                    location="brand_profile.typography",
                )
            )
        if not colors:
            issues.append(
                QualityIssue(
                    category="style",
                    description="Brand profile lacks color settings",
                    severity=IssueSeverity.MINOR,
                    location="brand_profile.colors",
                )
            )
        if metadata.get("format") is None and metadata.get("output_format") is None:
            issues.append(
                QualityIssue(
                    category="style",
                    description="Rendered artifact metadata lacks output format",
                    severity=IssueSeverity.INFO,
                    location="render_result.metadata",
                )
            )
        return issues
