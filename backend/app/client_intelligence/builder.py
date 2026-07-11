from app.client_intelligence.analyzer import ClientIntelligenceAnalyzer
from app.client_intelligence.interfaces.intelligence import ClientIntelligenceBuilderInterface
from app.client_intelligence.models import ClientIntelligenceSources, ClientProfile, IntelligenceSignal
from app.client_intelligence.profiles.profile_builder import ProfileBuilder


class ClientIntelligenceBuilder(ClientIntelligenceBuilderInterface):
    """Builds ClientProfile from existing system fragments — no persistence."""

    def __init__(
        self,
        analyzer: ClientIntelligenceAnalyzer | None = None,
        profile_builder: ProfileBuilder | None = None,
    ) -> None:
        self._analyzer = analyzer or ClientIntelligenceAnalyzer()
        self._profile_builder = profile_builder or ProfileBuilder()

    def build(
        self,
        sources: ClientIntelligenceSources,
        *,
        llm_enrichment: dict | None = None,
    ) -> ClientProfile:
        signals = self._analyzer.analyze_heuristics(sources)
        enrichment = llm_enrichment or {}
        extra_signals: list[IntelligenceSignal] = list(enrichment.get("signals") or [])
        if enrichment.get("risks"):
            for risk in enrichment["risks"]:
                extra_signals.append(
                    IntelligenceSignal(
                        category="risk",
                        key="llm_risk",
                        value=str(risk),
                        confidence=float(enrichment.get("confidence") or 0.7),
                        source="llm_analyzer",
                    )
                )
        merged = _merge_signals(signals, extra_signals)
        return self._profile_builder.build(
            sources,
            merged,
            summary=enrichment.get("summary"),
            industry=enrichment.get("industry"),
            services=list(enrichment.get("services") or []) or None,
            recommendations=list(enrichment.get("recommendations") or []) or None,
            confidence=enrichment.get("confidence"),
        )


def _merge_signals(
    primary: list[IntelligenceSignal],
    secondary: list[IntelligenceSignal],
) -> list[IntelligenceSignal]:
    seen: set[tuple[str, str, str]] = set()
    result: list[IntelligenceSignal] = []
    for signal in primary + secondary:
        key = (signal.category, signal.key, signal.value)
        if key in seen or not signal.value:
            continue
        seen.add(key)
        result.append(signal)
    return result
