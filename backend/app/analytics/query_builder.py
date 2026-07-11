from app.analytics.models import AnalyticsDataset, AnalyticsRequest
from app.analytics.providers.data_provider import CompositeAnalyticsDataProvider


class AnalyticsQueryBuilder:
    """Builds a read-only analytics dataset from request + providers."""

    def __init__(self, provider: CompositeAnalyticsDataProvider | None = None) -> None:
        self._provider = provider or CompositeAnalyticsDataProvider()

    async def build(self, request: AnalyticsRequest) -> AnalyticsDataset:
        return await self._provider.collect(request)
