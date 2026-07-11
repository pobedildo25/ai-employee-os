from app.analytics.models import AnalyticsDataset, AnalyticsInsight


class QualityAnalyzer:
    def analyze(self, dataset: AnalyticsDataset, metrics: dict) -> list[AnalyticsInsight]:
        insights: list[AnalyticsInsight] = []
        quality = metrics.get("quality") or {}
        pass_rate = float(quality.get("pass_rate") or 0.0)
        revision_rate = float(quality.get("revision_rate") or 0.0)
        if quality.get("quality_reviews") or dataset.revisions or dataset.artifacts:
            if pass_rate >= 0.8:
                insights.append(
                    AnalyticsInsight(
                        category="quality",
                        title="Strong quality pass rate",
                        description="Documents usually pass quality review",
                        importance=0.7,
                        confidence=0.8,
                    )
                )
            elif revision_rate >= 0.3:
                insights.append(
                    AnalyticsInsight(
                        category="quality",
                        title="Elevated revision rate",
                        description=f"Revision rate is {revision_rate:.0%} — investigate recurring feedback",
                        importance=0.8,
                        confidence=0.75,
                    )
                )
            else:
                insights.append(
                    AnalyticsInsight(
                        category="quality",
                        title="Quality overview",
                        description=f"Pass rate {pass_rate:.0%}, revision rate {revision_rate:.0%}",
                        importance=0.55,
                        confidence=0.7,
                    )
                )
        return insights
