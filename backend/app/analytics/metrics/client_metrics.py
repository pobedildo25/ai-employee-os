from typing import Any

from app.analytics.models import AnalyticsDataset


def compute_client_metrics(dataset: AnalyticsDataset) -> dict[str, Any]:
    completed_tasks = sum(
        1
        for task in dataset.tasks
        if str(task.get("status") or "").lower() in {"completed", "done", "closed", "success"}
    )
    return {
        "projects_count": len(dataset.projects),
        "artifacts_count": len(dataset.artifacts),
        "completed_tasks": completed_tasks,
        "revisions_count": len(dataset.revisions),
        "tasks_count": len(dataset.tasks),
    }
