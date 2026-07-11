import json

from app.research.models import ResearchType

RESEARCH_SYSTEM_PROMPT = """You are a Research analyst for AI Employee OS.
Interpret collected sources — do not browse the web yourself.
Return ONLY valid JSON with findings, insights, and recommendations.
Prefer evidence grounded in provided sources.
Research feeds Strategy later; do not produce strategy plans here.
"""


def build_research_user_message(
    *,
    query: str,
    research_type: ResearchType | str,
    sources: list[dict],
    heuristic_insights: list[dict],
    context: dict,
    constraints: list[str],
) -> str:
    payload = {
        "query": query,
        "research_type": str(research_type),
        "sources": sources[:12],
        "heuristic_insights": heuristic_insights,
        "client_intelligence": context.get("client_intelligence_context")
        or context.get("client_intelligence"),
        "strategy_context": context.get("strategy_result") or context.get("strategy_context"),
        "constraints": constraints,
        "response_schema": {
            "summary": "string",
            "findings": [{"title": "string", "description": "string", "source_urls": [], "confidence": 0.0}],
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
        "Analyze research sources and return JSON.\n"
        f"{json.dumps(payload, ensure_ascii=False, default=str)}"
    )
