from datetime import datetime

from app.research.models import ResearchSource


class SourceRanker:
    """Soft ranking by relevance, credibility, freshness — no hard domain rules."""

    def rank(self, sources: list[ResearchSource], *, query: str) -> list[ResearchSource]:
        ranked = [self._score(source, query=query) for source in sources]
        ranked.sort(
            key=lambda item: (
                0.45 * item.relevance_score
                + 0.35 * item.credibility_score
                + 0.20 * item.freshness_score
            ),
            reverse=True,
        )
        return ranked

    def _score(self, source: ResearchSource, *, query: str) -> ResearchSource:
        relevance = _relevance(source, query)
        freshness = _freshness(source.published_at)
        credibility = min(1.0, max(0.0, source.credibility_score))
        return source.model_copy(
            update={
                "relevance_score": relevance,
                "freshness_score": freshness,
                "credibility_score": credibility,
            }
        )


def _relevance(source: ResearchSource, query: str) -> float:
    text = f"{source.title} {source.extracted_content}".lower()
    tokens = [token for token in query.lower().split() if len(token) > 2]
    if not tokens:
        return 0.5
    hits = sum(1 for token in tokens if token in text)
    return min(1.0, 0.35 + hits / max(1, len(tokens)))


def _freshness(published_at: datetime | None) -> float:
    if published_at is None:
        return 0.5
    age_days = max(0.0, (datetime.utcnow() - published_at.replace(tzinfo=None)).total_seconds() / 86400)
    if age_days <= 7:
        return 0.95
    if age_days <= 30:
        return 0.8
    if age_days <= 180:
        return 0.6
    return 0.4
