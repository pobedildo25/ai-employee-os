import json

from app.analytics.models import AnalyticsType

ANALYTICS_SYSTEM_PROMPT = """You are an Analytics interpreter for AI Employee OS.
Interpret provided metrics and heuristic insights — do not invent CRM storage.
Return ONLY valid JSON.
Honor learning_rules (e.g. prefer reports without tables when requested).
Do not create presentation layouts — analytics only; presentation is a separate skill.
"""


def build_analytics_user_message(
    *,
    analytics_type: AnalyticsType | str,
    metrics: dict,
    heuristic_insights: list[dict],
    client_intelligence: dict,
    learning_rules: list[dict],
    goal: str | None,
) -> str:
    payload = {
        "goal": goal,
        "analytics_type": str(analytics_type),
        "metrics": metrics,
        "heuristic_insights": heuristic_insights,
        "client_intelligence": client_intelligence,
        "learning_rules": learning_rules,
        "response_schema": {
            "summary": "string",
            "insights": [
                {
                    "category": "string",
                    "title": "string",
                    "description": "string",
                    "importance": 0.0,
                    "confidence": 0.0,
                }
            ],
            "recommendations": ["string"],
            "confidence": 0.0,
        },
    }
    return (
        "Interpret analytics metrics and return JSON insights/recommendations.\n"
        f"{json.dumps(payload, ensure_ascii=False, default=str)}"
    )
