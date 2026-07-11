from app.research.models import ResearchInsight, ResearchSource


class CompanyAnalyzer:
    def analyze(self, sources: list[ResearchSource], *, query: str) -> list[ResearchInsight]:
        insights: list[ResearchInsight] = []
        if sources:
            insights.append(
                ResearchInsight(
                    category="company",
                    title="Company profile signals",
                    description=f"Collected company-related evidence for '{query}'",
                    importance=0.55,
                    confidence=0.65,
                )
            )
        return insights
