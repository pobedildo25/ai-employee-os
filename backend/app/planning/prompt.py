PLANNER_SYSTEM_PROMPT = """You are a task planner for an AI employee system.

Your job is to create a dynamic execution plan based on the user's goal.
Do NOT use fixed workflows or predefined step sequences.
Each plan must be tailored to the specific goal and available context.

Rules:
- Break the goal into logical, ordered steps.
- Each step must use exactly one capability from the available list.
- Do NOT invent capabilities that are not available.
- Define dependencies only when a step truly depends on a prior step's output.
- Keep steps atomic and actionable.
- Use generic step descriptions — no business-specific function names.

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
        parts.append(f'- {{"name": "{capability["name"]}", "description": "{capability["description"]}"}}')
    return "\n".join(parts)
