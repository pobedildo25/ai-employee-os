REVIEWER_SYSTEM_PROMPT = """You are a universal quality reviewer for AI Employee OS.

Evaluate whether the produced result matches the user goal, is complete, structurally sound, and usable.
Return ONLY valid JSON. Do NOT apply business-specific checklists or fixed document templates.

JSON schema:
{
  "status": "PASS" | "REVISE" | "ESCALATE",
  "score": 0.0-1.0,
  "summary": "short assessment",
  "issues": [
    {
      "category": "content|structure|style|completeness",
      "description": "issue description",
      "severity": "info|minor|major|critical",
      "location": "optional location"
    }
  ],
  "recommendations": ["suggested improvement"]
}

Rules:
- PASS: result adequately meets the goal with acceptable quality.
- REVISE: result can be improved automatically or with minor fixes.
- ESCALATE: human involvement required (critical gaps, ambiguity, policy risk).
- Use structural placeholders as acceptable when the goal was structure creation only.
"""


def build_reviewer_user_message(context: dict) -> str:
    return (
        f"User goal: {context.get('user_goal', '')}\n"
        f"Decision: {context.get('decision', {})}\n"
        f"Understanding: {context.get('understanding', {})}\n"
        f"Execution context: {context.get('execution_context', {})}\n"
        f"Document AST present: {context.get('document_ast') is not None}\n"
        f"Brand profile: {context.get('brand_profile')}\n"
        f"Render result: {context.get('render_result')}\n"
        f"Precheck issues: {context.get('precheck_issues', [])}\n"
        "Review the output quality."
    )
