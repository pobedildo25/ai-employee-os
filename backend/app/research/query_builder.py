from app.research.models import ResearchRequest, ResearchType


class ResearchQueryBuilder:
    """Builds search queries from goal + context — no keyword routing."""

    def build(self, request: ResearchRequest) -> list[str]:
        queries: list[str] = []
        base = request.query.strip()
        if base:
            queries.append(base)

        context = request.context or {}
        client = context.get("client_intelligence_context") or context.get("client_intelligence") or {}
        strategy = context.get("strategy_result") or context.get("strategy_context") or {}
        client_ctx = context.get("client_context") or {}

        industry = client.get("industry") or client_ctx.get("industry")
        if industry and base:
            queries.append(f"{base} in {industry}")

        summary = client.get("summary")
        if summary and base:
            queries.append(f"{base} for {str(summary)[:80]}")

        strategy_type = strategy.get("strategy_type") or strategy.get("type")
        if strategy_type and base:
            queries.append(f"{base} {strategy_type} implications")

        type_hint = _type_hint(request.research_type)
        if type_hint and base:
            queries.append(f"{base} {type_hint}")

        for constraint in request.constraints[:3]:
            if constraint.strip():
                queries.append(f"{base} {constraint.strip()}")

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for query in queries:
            key = query.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(query)
        return unique or [base or "general research"]


def _type_hint(research_type: ResearchType) -> str:
    mapping = {
        ResearchType.MARKET_RESEARCH: "market size demand outlook",
        ResearchType.COMPETITOR_RESEARCH: "competitors comparison positioning",
        ResearchType.COMPANY_RESEARCH: "company profile products leadership",
        ResearchType.TREND_ANALYSIS: "emerging trends adoption signals",
        ResearchType.CONTENT_RESEARCH: "content themes audience interest",
    }
    return mapping.get(research_type, "")
