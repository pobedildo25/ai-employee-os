from app.client_intelligence.analyzers.preference_analyzer import _dedupe, _iter_texts
from app.client_intelligence.models import ClientIntelligenceSources, IntelligenceSignal


class RiskAnalyzer:
    """Finds constraints and approval requirements — soft heuristics only."""

    def analyze(self, sources: ClientIntelligenceSources) -> list[IntelligenceSignal]:
        signals: list[IntelligenceSignal] = []
        for item in _iter_texts(sources):
            lower = item.lower()
            if any(token in lower for token in ("approval", "согласован", "approve", "утвержд")):
                signals.append(
                    IntelligenceSignal(
                        category="risk",
                        key="publication_gate",
                        value="Requires approval before publication",
                        confidence=0.85,
                        source="risk_analyzer",
                    )
                )
            if any(token in lower for token in ("legal", "юридич", "compliance", "ндa", "nda")):
                signals.append(
                    IntelligenceSignal(
                        category="risk",
                        key="compliance",
                        value="Compliance/legal review may be required",
                        confidence=0.7,
                        source="risk_analyzer",
                    )
                )
            if any(token in lower for token in ("срочно", "deadline", "дедлайн", "urgent")):
                signals.append(
                    IntelligenceSignal(
                        category="risk",
                        key="timeline_pressure",
                        value="Tight deadlines observed",
                        confidence=0.65,
                        source="risk_analyzer",
                    )
                )
        return _dedupe(signals)
