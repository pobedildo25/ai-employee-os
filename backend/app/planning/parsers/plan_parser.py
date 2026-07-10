import json
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.agents.parsers.response_parser import ResponseParseError, extract_json_content
from app.planning.models import PlanStep, TaskPlan


def parse_task_plan(raw: str) -> TaskPlan:
    content = extract_json_content(raw)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ResponseParseError(f"Invalid JSON: {exc}") from exc

    steps_data = data.pop("steps", [])
    step_ids: list[UUID] = []

    try:
        plan = TaskPlan(
            id=uuid4(),
            goal=data.get("goal", ""),
            summary=data.get("summary", ""),
            required_capabilities=data.get("required_capabilities", []),
            steps=[],
        )

        for index, step_data in enumerate(steps_data):
            step_id = uuid4()
            step_ids.append(step_id)
            dependency_indices = step_data.get("dependencies", [])
            dependencies = [
                step_ids[dep_index]
                for dep_index in dependency_indices
                if isinstance(dep_index, int) and 0 <= dep_index < len(step_ids)
            ]
            plan.steps.append(
                PlanStep(
                    id=step_id,
                    description=step_data.get("description", ""),
                    capability=step_data.get("capability", ""),
                    dependencies=dependencies,
                )
            )
    except (ValidationError, IndexError, TypeError) as exc:
        raise ResponseParseError(f"Schema validation failed: {exc}") from exc

    return plan
