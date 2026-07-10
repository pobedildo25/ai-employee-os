import json
import re

from pydantic import ValidationError

from app.agents.executive.models import ExecutiveAgentResult


class ResponseParseError(Exception):
    """Raised when LLM response cannot be parsed into a valid schema."""


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def extract_json_content(raw: str) -> str:
    text = raw.strip()
    match = _JSON_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    return text


def parse_executive_response(raw: str) -> ExecutiveAgentResult:
    content = extract_json_content(raw)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ResponseParseError(f"Invalid JSON: {exc}") from exc

    try:
        return ExecutiveAgentResult.model_validate(data)
    except ValidationError as exc:
        raise ResponseParseError(f"Schema validation failed: {exc}") from exc
