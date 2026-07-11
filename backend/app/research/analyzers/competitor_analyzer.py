from app.research.models import ResearchInsight, ResearchSource


class CompetitorAnalyzer:
    def analyze(self, sources: list[ResearchSource], *, query: str) -> list[ResearchInsight]:
        insights: list[ResearchInsight] = []
        competitorish = [
            s
            for s in sources
            if any(
                t in (s.title + " " + s.extracted_content).lower()
                for t in ("competitor", "launched", "vs", "rival")
            )
        ]
        if competitorish:
            insights.append(
                ResearchInsight(
                    category="competitor",
                    title="Competitive movement",
                    description=competitorish[0].extracted_content[:220]
                    or "Competitor activity detected",
                    importance=0.8,
                    confidence=0.7,
                )
            )
        return insights
