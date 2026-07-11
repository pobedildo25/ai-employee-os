from typing import Any

from app.analytics.models import AnalyticsDataset


def compute_execution_metrics(dataset: AnalyticsDataset) -> dict[str, Any]:
    executions = dataset.executions
    failures = [
        item
        for item in executions
        if str(item.get("status") or "").lower() in {"failed", "error", "failure"}
    ]
    durations = [
        float(item["duration_ms"])
        for item in executions
        if isinstance(item.get("duration_ms"), (int, float))
    ]
    avg_duration = sum(durations) / len(durations) if durations else 0.0
    return {
        "executions_count": len(executions),
        "avg_duration": avg_duration,
        "failures": len(failures),
        "failure_rate": (len(failures) / len(executions)) if executions else 0.0,
    }


def compute_quality_metrics(dataset: AnalyticsDataset) -> dict[str, Any]:
    results = dataset.quality_results
    if not results:
        revision_rate = min(1.0, len(dataset.revisions) / max(1, len(dataset.artifacts) or 1))
        return {
            "pass_rate": max(0.0, 1.0 - revision_rate) if dataset.revisions or dataset.artifacts else 0.0,
            "revision_rate": revision_rate if dataset.revisions else 0.0,
            "quality_reviews": 0,
        }
    passed = [
        item
        for item in results
        if bool(item.get("passed"))
        or str(item.get("status") or "").upper() in {"PASS", "PASSED"}
    ]
    revision_like = [
        item
        for item in results
        if str(item.get("status") or "").upper() in {"REVISE", "REVISION"}
        or bool(item.get("needs_revision"))
    ]
    total = len(results) or 1
    return {
        "pass_rate": len(passed) / total,
        "revision_rate": len(revision_like) / total,
        "quality_reviews": len(results),
    }
