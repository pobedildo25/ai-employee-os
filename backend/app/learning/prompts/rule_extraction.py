RULE_EXTRACTION_SYSTEM_PROMPT = """\
You extract durable behavior rules for an AI employee from user feedback.
Return ONLY valid JSON matching:
{
  "should_learn": true|false,
  "confidence": 0.0-1.0,
  "reason": "short reason",
  "rule": {
    "category": "string",
    "key": "string",
    "value": "string",
    "confidence": 0.0-1.0,
    "scope": "client"|"project"|"global"
  }
}
Allowed categories ONLY: style, writing_style, document_style, presentation_style,
format, formatting, language, tone, layout, structure, verbosity, preference,
brand, agency_practice, visual, copy.
Never extract rules about strategy, routing, decision type, capabilities, plans, or workflows.
Rules describe lasting preferences (style, verbosity, formatting), NOT one-off task edits.
If feedback is a temporary instruction or out of allowed categories, set should_learn=false and rule=null.
"""


def build_rule_extraction_message(
    *,
    feedback: str,
    source: str,
    context: dict | None = None,
) -> str:
    ctx = context or {}
    return (
        f"source: {source}\n"
        f"feedback: {feedback}\n"
        f"context: {ctx}\n"
        "Extract a durable learning rule if appropriate."
    )
