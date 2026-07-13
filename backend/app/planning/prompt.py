PLANNER_SYSTEM_PROMPT = """You are a task planner for an AI employee system.

Your job is to create a dynamic execution plan ONLY for multi-stage goals that need
ordered coordination across dependent capabilities.

Rules:
- You are invoked only when the goal genuinely requires multiple dependent stages.
- Break the goal into logical, ordered steps.
- Each step must use exactly one capability from the available list.
- Do NOT invent capabilities that are not available.
- Define dependencies only when a step truly depends on a prior step's output.
- Keep steps atomic and actionable.
- Prefer the minimum number of steps that still covers the goal.
- If the goal can be done in one capability step, return exactly one step
  (the runtime will treat it as direct execution).

Return ONLY valid JSON:
{
  "goal": "string — plan goal",
  "summary": "string — brief plan summary",
  "required_capabilities": ["string"],
  "steps": [
    {
      "description": "string — what this step accomplishes",
      "capability": "string — capability name from available list",
      "dependencies": []
    }
  ]
}

Note: dependencies reference step indices (0-based) in the steps array, not UUIDs.
"""


def build_planner_user_message(
    understanding: dict,
    context: dict,
    capabilities: list[dict[str, str]],
) -> str:
    parts = [
        f"Goal:\n{understanding.get('goal', '')}",
        f"\nSummary:\n{understanding.get('summary', '')}",
        f"\nSuggested capabilities:\n{understanding.get('required_capabilities', [])}",
        f"\nMissing information:\n{understanding.get('missing_information', [])}",
        f"\nExecution context:\n{context}",
        "\nAvailable capabilities:",
    ]
    for capability in capabilities:
        parts.append(
            f'- {{"name": "{capability["name"]}", "description": "{capability["description"]}"}}'
        )
    return "\n".join(parts)
