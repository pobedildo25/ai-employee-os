from app.client_intelligence.models import ClientIntelligenceSources, ClientProfile, IntelligenceSignal


class ProfileBuilder:
    """Assembles ClientProfile from analyzer signals and source fragments."""

    def build(
        self,
        sources: ClientIntelligenceSources,
        signals: list[IntelligenceSignal],
        *,
        summary: str | None = None,
        industry: str | None = None,
        services: list[str] | None = None,
        recommendations: list[str] | None = None,
        confidence: float | None = None,
    ) -> ClientProfile:
        preferences: dict = {}
        communication: dict = {}
        risks: list[str] = []
        successful: list[str] = []

        for signal in signals:
            if signal.category == "preference":
                preferences[signal.key] = signal.value
            elif signal.category == "communication":
                communication[signal.key] = signal.value
            elif signal.category == "risk":
                risks.append(signal.value)
            elif signal.category == "history" and signal.key.startswith("successful"):
                successful.append(signal.value)

        brand = None
        if sources.brand_profiles:
            brand = sources.brand_profiles[0]
        elif sources.execution_context.get("brand_profile"):
            brand = sources.execution_context.get("brand_profile")

        client_name = (
            sources.client_context.get("name")
            or sources.client_context.get("title")
            or "Client"
        )
        description = sources.client_context.get("description") or ""
        default_summary = summary or (
            f"{client_name}" + (f" — {description}" if description else " profile from existing context")
        )

        sources_used = []
        if sources.client_context:
            sources_used.append("client")
        if sources.memory_items:
            sources_used.append("memory")
        if sources.knowledge_items:
            sources_used.append("knowledge")
        if sources.learning_rules:
            sources_used.append("learning")
        if sources.workspace:
            sources_used.append("workspace")
        if sources.projects:
            sources_used.append("projects")
        if sources.artifacts:
            sources_used.append("artifacts")
        if sources.brand_profiles or brand:
            sources_used.append("brand")

        confidences = [s.confidence for s in signals] or [0.4]
        computed = confidence if confidence is not None else min(0.95, sum(confidences) / len(confidences))

        return ClientProfile(
            client_id=sources.client_id,
            summary=default_summary,
            industry=industry or sources.client_context.get("industry"),
            services=services or list(sources.client_context.get("services") or []),
            preferences=preferences,
            communication_style=communication,
            brand_profile=brand if isinstance(brand, dict) else None,
            previous_projects=list(sources.projects),
            successful_patterns=successful,
            risks=_unique(risks),
            recommendations=recommendations or _default_recommendations(preferences, risks),
            confidence=round(computed, 3),
            metadata={
                "workspace_active_project_id": sources.workspace.get("active_project_id"),
                "workspace_active_artifact_id": sources.workspace.get("active_artifact_id"),
            },
            signals=signals,
            sources_used=sources_used,
        )


def _default_recommendations(preferences: dict, risks: list[str]) -> list[str]:
    recs: list[str] = []
    if preferences.get("verbosity") == "short" or preferences.get("presentation_length") == "short":
        recs.append("Keep deliverables concise")
    if preferences.get("document_style") == "minimal":
        recs.append("Prefer minimal document layouts")
    if preferences.get("language") == "formal":
        recs.append("Use formal communication tone")
    for risk in risks[:3]:
        recs.append(f"Account for risk: {risk}")
    if not recs:
        recs.append("Validate assumptions with the client before publishing")
    return recs


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
