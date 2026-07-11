from typing import Any

from app.analytics.metrics.client_metrics import compute_client_metrics
from app.analytics.metrics.execution_metrics import compute_execution_metrics, compute_quality_metrics
from app.analytics.metrics.project_metrics import compute_project_metrics
from app.analytics.models import AnalyticsDataset


def compute_all_metrics(dataset: AnalyticsDataset) -> dict[str, Any]:
    return {
        "client": compute_client_metrics(dataset),
        "project": compute_project_metrics(dataset),
        "execution": compute_execution_metrics(dataset),
        "quality": compute_quality_metrics(dataset),
    }
