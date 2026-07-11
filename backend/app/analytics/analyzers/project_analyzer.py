from app.analytics.models import AnalyticsDataset, AnalyticsInsight


class ProjectAnalyzer:
    def analyze(self, dataset: AnalyticsDataset, metrics: dict) -> list[AnalyticsInsight]:
        insights: list[AnalyticsInsight] = []
        project = metrics.get("project") or {}
        artifacts = int(project.get("artifacts_created") or 0)
        completed = int(project.get("tasks_completed") or 0)
        if artifacts:
            insights.append(
                AnalyticsInsight(
                    category="project",
                    title="Artifact output",
                    description=f"{artifacts} artifact(s) created across selected projects",
                    importance=0.55,
                    confidence=0.9,
                )
            )
        if completed:
            insights.append(
                AnalyticsInsight(
                    category="project",
                    title="Task completion",
                    description=f"{completed} task(s) marked completed",
                    importance=0.6,
                    confidence=0.85,
                )
            )
        active = [
            p
            for p in dataset.projects
            if str(p.get("status") or "").lower() in {"active", "in_progress", "open"}
        ]
        if active:
            insights.append(
                AnalyticsInsight(
                    category="project",
                    title="Active projects",
                    description=f"{len(active)} project(s) currently active",
                    importance=0.5,
                    confidence=0.8,
                )
            )
        return insights
