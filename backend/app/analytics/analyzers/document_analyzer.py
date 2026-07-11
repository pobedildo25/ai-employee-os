from app.analytics.models import AnalyticsDataset, AnalyticsInsight


class DocumentAnalyzer:
    def analyze(self, dataset: AnalyticsDataset, metrics: dict) -> list[AnalyticsInsight]:
        insights: list[AnalyticsInsight] = []
        by_type: dict[str, int] = {}
        for artifact in dataset.artifacts:
            kind = str(artifact.get("artifact_type") or "unknown")
            by_type[kind] = by_type.get(kind, 0) + 1
        if by_type:
            top = sorted(by_type.items(), key=lambda item: item[1], reverse=True)[0]
            insights.append(
                AnalyticsInsight(
                    category="document",
                    title="Dominant artifact type",
                    description=f"Most common artifact type is '{top[0]}' ({top[1]})",
                    importance=0.55,
                    confidence=0.85,
                )
            )
        completed = [
            a
            for a in dataset.artifacts
            if str(a.get("status") or "").lower() in {"completed", "ready", "published"}
        ]
        if completed:
            insights.append(
                AnalyticsInsight(
                    category="document",
                    title="Completed documents",
                    description=f"{len(completed)} document artifact(s) completed",
                    importance=0.5,
                    confidence=0.8,
                )
            )
        return insights
