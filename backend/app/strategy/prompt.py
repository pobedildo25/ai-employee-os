import json

from app.strategy.frameworks import section_hints_for
from app.strategy.models import StrategyType

STRATEGY_PLANNER_SYSTEM_PROMPT = """You are a Strategy Analyst for AI Employee OS.
Produce structured marketing/business strategy analysis — not styled documents.
Return ONLY valid JSON matching the schema.
Frameworks are structural scaffolds only — do not invent fixed business scripts.
Honor learning_rules (e.g. prefer short reports when requested).
Do NOT apply brand styling — pass brand_profile through metadata only.
Available strategy types: {strategy_types}
""".format(
    strategy_types=", ".join(item.value for item in StrategyType)
)


def build_planner_user_message(
    *,
    goal: str,
    client_context: dict,
    project_context: dict,
    audience: str | None,
    constraints: list[str],
    learning_rules: list[dict] | None,
    strategy_type: str | None,
    brand_profile: dict | None,
) -> str:
    hints = section_hints_for(strategy_type)
    payload = {
        "goal": goal,
        "client_context": client_context,
        "project_context": project_context,
        "audience": audience,
        "constraints": constraints,
        "learning_rules": learning_rules or [],
        "strategy_type_hint": strategy_type,
        "section_hints": hints,
        "brand_profile_present": bool(brand_profile),
        "response_schema": {
            "type": "marketing_strategy|swot_analysis|positioning|go_to_market|competitor_analysis|campaign_plan",
            "strategy_type": "same as type",
            "summary": "string",
            "insights": [
                {
                    "category": "string",
                    "title": "string",
                    "description": "string",
                    "confidence": 0.0,
                }
            ],
            "recommendations": ["string"],
            "sections": [{"title": "string", "paragraphs": ["string"]}],
            "framework_data": {},
            "missing_information": [],
            "metadata": {},
        },
    }
    return (
        "Produce a strategy analysis as JSON.\n"
        f"{json.dumps(payload, ensure_ascii=False)}\n"
        "Keep copy concise when learning_rules ask for short reports."
    )
