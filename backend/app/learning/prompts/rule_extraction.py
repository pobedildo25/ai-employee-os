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
Rules describe lasting preferences (style, verbosity, formatting), NOT one-off task edits.
If feedback is a temporary instruction, set should_learn=false and rule=null.
Do not invent business workflows.
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
