import json

from app.presentation_design.templates import all_slide_types, select_template_hint

PRESENTATION_PLANNER_SYSTEM_PROMPT = """You are a Presentation Designer for AI Employee OS.
Design presentation structure and storytelling — not pixel layouts.
Return ONLY valid JSON matching the schema.
Use existing Document AST concepts later: each slide becomes a SECTION.
Do NOT invent business-specific fixed scripts.
Templates are soft hints only — rearrange when the goal requires it.
Prefer concise slide copy. Include a clear CTA when appropriate.
Available slide types: {slide_types}
""".format(
    slide_types=", ".join(all_slide_types())
)


def build_planner_user_message(
    *,
    goal: str,
    context: dict,
    brand_profile: dict | None,
    learning_rules: list[dict] | None,
    presentation_type: str | None,
) -> str:
    hint = select_template_hint(presentation_type)
    payload = {
        "goal": goal,
        "context": context,
        "brand_profile": brand_profile,
        "learning_rules": learning_rules or [],
        "presentation_type_hint": presentation_type,
        "template_hint": hint,
        "response_schema": {
            "title": "string",
            "goal": "string",
            "audience": "string|null",
            "presentation_type": "business|sales|marketing|pitch|custom",
            "slides": [
                {
                    "order": 0,
                    "slide_type": "TITLE|PROBLEM|SOLUTION|...",
                    "title": "string",
                    "purpose": "string",
                    "content_blocks": [{"kind": "paragraph|bullet", "text": "string"}],
                    "visual_notes": "string|null",
                }
            ],
            "metadata": {},
            "missing_information": [],
        },
    }
    return (
        "Design a presentation plan as JSON.\n"
        f"{json.dumps(payload, ensure_ascii=False)}\n"
        "Honor learning_rules when present (e.g. minimal text)."
    )
