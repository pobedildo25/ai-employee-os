from app.research.models import ResearchInsight, ResearchSource


class MarketAnalyzer:
    def analyze(self, sources: list[ResearchSource], *, query: str) -> list[ResearchInsight]:
        insights: list[ResearchInsight] = []
        growth = [
            s
            for s in sources
            if any(t in s.extracted_content.lower() for t in ("growth", "demand", "growing"))
        ]
        if growth:
            insights.append(
                ResearchInsight(
                    category="market",
                    title="Demand signal",
                    description=f"Sources indicate growing demand related to '{query}'",
                    importance=0.75,
                    confidence=0.7,
                )
            )
        if sources:
            insights.append(
                ResearchInsight(
                    category="market",
                    title="Market coverage",
                    description=f"Reviewed {len(sources)} market-oriented source(s)",
                    importance=0.5,
                    confidence=0.85,
                )
            )
        return insights
