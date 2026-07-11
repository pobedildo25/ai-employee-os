from typing import Any

from app.analytics.models import AnalyticsDataset


def compute_project_metrics(dataset: AnalyticsDataset) -> dict[str, Any]:
    durations = []
    for project in dataset.projects:
        created = project.get("created_at")
        updated = project.get("updated_at")
        if created and updated:
            try:
                durations.append(max(0.0, (updated - created).total_seconds()))
            except TypeError:
                pass
    avg_duration = sum(durations) / len(durations) if durations else 0.0
    completed_tasks = sum(
        1
        for task in dataset.tasks
        if str(task.get("status") or "").lower() in {"completed", "done", "closed", "success"}
    )
    return {
        "duration": avg_duration,
        "tasks_completed": completed_tasks,
        "artifacts_created": len(dataset.artifacts),
        "projects_count": len(dataset.projects),
    }
