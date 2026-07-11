from app.client_intelligence.models import ClientProfile
from app.quality.models import IssueSeverity, QualityIssue


class ProfileValidator:
    """Quality checks for client intelligence profiles."""

    def validate(self, profile: ClientProfile) -> list[str]:
        warnings: list[str] = []
        if not str(profile.client_id).strip():
            warnings.append("client_id is required")
        if not profile.summary.strip():
            warnings.append("summary is missing")
        if profile.confidence < 0.3:
            warnings.append("confidence is low")
        if not profile.sources_used:
            warnings.append("no sources tracked")
        completeness = self.completeness_score(profile)
        if completeness < 0.35:
            warnings.append("profile completeness is low")
        return warnings

    def completeness_score(self, profile: ClientProfile) -> float:
        checks = [
            bool(profile.summary),
            bool(profile.preferences),
            bool(profile.communication_style),
            bool(profile.previous_projects) or bool(profile.successful_patterns),
            bool(profile.risks) or bool(profile.recommendations),
            bool(profile.sources_used),
        ]
        return sum(1 for item in checks if item) / len(checks)

    def quality_issues(self, profile: ClientProfile | None) -> list[QualityIssue]:
        if profile is None:
            return [
                QualityIssue(
                    category="content",
                    description="client profile missing",
                    severity=IssueSeverity.MAJOR,
                    location="client_intelligence",
                )
            ]
        issues: list[QualityIssue] = []
        for warning in self.validate(profile):
            severity = IssueSeverity.MINOR
            if "required" in warning or "missing" in warning:
                severity = IssueSeverity.MAJOR
            issues.append(
                QualityIssue(
                    category="content",
                    description=warning,
                    severity=severity,
                    location="client_profile",
                )
            )
        if not profile.sources_used:
            issues.append(
                QualityIssue(
                    category="structure",
                    description="source tracking missing",
                    severity=IssueSeverity.MAJOR,
                    location="client_profile.sources_used",
                )
            )
        return issues
