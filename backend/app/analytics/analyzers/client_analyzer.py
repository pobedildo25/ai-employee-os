from app.analytics.models import AnalyticsDataset, AnalyticsInsight


class ClientAnalyzer:
    def analyze(self, dataset: AnalyticsDataset, metrics: dict) -> list[AnalyticsInsight]:
        insights: list[AnalyticsInsight] = []
        client = metrics.get("client") or {}
        projects = int(client.get("projects_count") or 0)
        if projects:
            insights.append(
                AnalyticsInsight(
                    category="client",
                    title="Project portfolio",
                    description=f"Client has {projects} tracked project(s)",
                    importance=0.6,
                    confidence=0.9,
                )
            )
        if dataset.client_intelligence.get("summary"):
            insights.append(
                AnalyticsInsight(
                    category="client",
                    title="Client intelligence",
                    description=str(dataset.client_intelligence["summary"]),
                    importance=0.7,
                    confidence=float(dataset.client_intelligence.get("confidence") or 0.7),
                )
            )
        risks = dataset.client_intelligence.get("risks") or []
        for risk in risks[:3]:
            insights.append(
                AnalyticsInsight(
                    category="client",
                    title="Known client risk",
                    description=str(risk),
                    importance=0.8,
                    confidence=0.75,
                )
            )
        return insights
