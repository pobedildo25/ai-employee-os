from app.research.analyzers.company_analyzer import CompanyAnalyzer
from app.research.analyzers.competitor_analyzer import CompetitorAnalyzer
from app.research.analyzers.market_analyzer import MarketAnalyzer
from app.research.analyzers.trend_analyzer import TrendAnalyzer
from app.research.models import ResearchInsight, ResearchSource, ResearchType


def run_type_analyzers(
    research_type: ResearchType,
    sources: list[ResearchSource],
    *,
    query: str,
) -> list[ResearchInsight]:
    insights: list[ResearchInsight] = []
    if research_type in {ResearchType.MARKET_RESEARCH, ResearchType.CONTENT_RESEARCH}:
        insights.extend(MarketAnalyzer().analyze(sources, query=query))
    if research_type == ResearchType.COMPETITOR_RESEARCH:
        insights.extend(CompetitorAnalyzer().analyze(sources, query=query))
    if research_type == ResearchType.COMPANY_RESEARCH:
        insights.extend(CompanyAnalyzer().analyze(sources, query=query))
    if research_type == ResearchType.TREND_ANALYSIS:
        insights.extend(TrendAnalyzer().analyze(sources, query=query))
    if not insights:
        insights.extend(MarketAnalyzer().analyze(sources, query=query))
        insights.extend(TrendAnalyzer().analyze(sources, query=query))
    return insights
