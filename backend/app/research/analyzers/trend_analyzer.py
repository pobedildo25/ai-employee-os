from app.research.models import ResearchInsight, ResearchSource


class TrendAnalyzer:
    def analyze(self, sources: list[ResearchSource], *, query: str) -> list[ResearchInsight]:
        insights: list[ResearchInsight] = []
        trendy = [
            s
            for s in sources
            if any(
                t in (s.title + " " + s.extracted_content).lower()
                for t in ("trend", "emerging", "adoption")
            )
        ]
        if trendy:
            insights.append(
                ResearchInsight(
                    category="trend",
                    title="Emerging trend",
                    description=trendy[0].extracted_content[:220] or f"Trend signals around {query}",
                    importance=0.7,
                    confidence=0.68,
                )
            )
        return insights
