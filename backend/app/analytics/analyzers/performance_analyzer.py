from app.analytics.models import AnalyticsDataset, AnalyticsInsight


class PerformanceAnalyzer:
    def analyze(self, dataset: AnalyticsDataset, metrics: dict) -> list[AnalyticsInsight]:
        insights: list[AnalyticsInsight] = []
        execution = metrics.get("execution") or {}
        failures = int(execution.get("failures") or 0)
        count = int(execution.get("executions_count") or 0)
        if count:
            insights.append(
                AnalyticsInsight(
                    category="performance",
                    title="Execution volume",
                    description=f"{count} execution(s) observed",
                    importance=0.5,
                    confidence=0.9,
                )
            )
        if failures:
            insights.append(
                AnalyticsInsight(
                    category="performance",
                    title="Execution failures",
                    description=f"{failures} failed execution(s) — investigate recurring errors",
                    importance=0.85,
                    confidence=0.8,
                )
            )
        avg = float(execution.get("avg_duration") or 0.0)
        if avg > 0:
            insights.append(
                AnalyticsInsight(
                    category="performance",
                    title="Average duration",
                    description=f"Average execution duration is {avg:.0f} ms",
                    importance=0.45,
                    confidence=0.75,
                )
            )
        return insights
