from app.client_intelligence.analyzers.preference_analyzer import _dedupe, _iter_texts
from app.client_intelligence.models import ClientIntelligenceSources, IntelligenceSignal


class CommunicationAnalyzer:
    """Infers tone/language/format — soft heuristics only."""

    def analyze(self, sources: ClientIntelligenceSources) -> list[IntelligenceSignal]:
        signals: list[IntelligenceSignal] = []
        for item in _iter_texts(sources):
            lower = item.lower()
            if any(token in lower for token in ("professional", "профессион", "делов")):
                signals.append(
                    IntelligenceSignal(
                        category="communication",
                        key="tone",
                        value="professional",
                        confidence=0.75,
                        source="communication_analyzer",
                    )
                )
            if any(token in lower for token in ("short", "коротк", "brief", "кратк")):
                signals.append(
                    IntelligenceSignal(
                        category="communication",
                        key="verbosity",
                        value="short",
                        confidence=0.8,
                        source="communication_analyzer",
                    )
                )
            if any(token in lower for token in ("email", "почт", "telegram", "чат")):
                channel = "email" if "email" in lower or "почт" in lower else "chat"
                signals.append(
                    IntelligenceSignal(
                        category="communication",
                        key="channel",
                        value=channel,
                        confidence=0.65,
                        source="communication_analyzer",
                    )
                )
        return _dedupe(signals)
