from app.client_intelligence.analyzers.preference_analyzer import _dedupe
from app.client_intelligence.models import ClientIntelligenceSources, IntelligenceSignal


class HistoryAnalyzer:
    """Looks at past projects/artifacts/patterns — soft heuristics only."""

    def analyze(self, sources: ClientIntelligenceSources) -> list[IntelligenceSignal]:
        signals: list[IntelligenceSignal] = []
        if sources.projects:
            signals.append(
                IntelligenceSignal(
                    category="history",
                    key="project_count",
                    value=str(len(sources.projects)),
                    confidence=0.9,
                    source="history_analyzer",
                )
            )
            completed = [
                p
                for p in sources.projects
                if str(p.get("status") or "").lower() in {"completed", "done", "closed"}
            ]
            if completed:
                signals.append(
                    IntelligenceSignal(
                        category="history",
                        key="successful_projects",
                        value=str(len(completed)),
                        confidence=0.75,
                        source="history_analyzer",
                    )
                )
        for artifact in sources.artifacts[:10]:
            name = str(artifact.get("name") or artifact.get("artifact_type") or "artifact")
            status = str(artifact.get("status") or "")
            if status.lower() in {"completed", "ready", "published"}:
                signals.append(
                    IntelligenceSignal(
                        category="history",
                        key="successful_artifact",
                        value=name,
                        confidence=0.7,
                        source="history_analyzer",
                    )
                )
        for item in sources.memory_items:
            if str(item.get("type") or "").upper() == "DECISION":
                signals.append(
                    IntelligenceSignal(
                        category="history",
                        key="past_decision",
                        value=str(item.get("content") or "")[:200],
                        confidence=float(item.get("importance") or 0.6),
                        source="memory",
                    )
                )
        return _dedupe(signals)
