import json

from app.core.config import Settings
from app.llm.gateway import LLMGateway
from app.llm.models import LLMResponse
from tests.test_llm_gateway import MockProvider


def executive_json(
    *,
    goal: str,
    summary: str,
    action: str,
    required_capabilities: list[str] | None = None,
    missing_information: list[str] | None = None,
    next_action: str = "respond",
    response_message: str | None = None,
    clarification_question: str | None = None,
    reasoning: str = "test reasoning",
) -> str:
    payload = {
        "understanding": {
            "goal": goal,
            "summary": summary,
            "required_capabilities": required_capabilities or [],
            "missing_information": missing_information or [],
            "next_action": next_action,
        },
        "decision": {
            "action": action,
            "reasoning": reasoning,
            "response_message": response_message,
            "clarification_question": clarification_question,
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def plan_json(
    *,
    goal: str = "test goal",
    summary: str = "test summary",
    steps: list[dict] | None = None,
) -> str:
    payload = {
        "goal": goal,
        "summary": summary,
        "required_capabilities": ["document_generation"],
        "steps": steps
        or [
            {"description": "Analyze materials", "capability": "document_analysis", "dependencies": []},
            {
                "description": "Generate document",
                "capability": "document_generation",
                "dependencies": [0],
            },
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def mock_gateway(settings: Settings, *responses: str) -> tuple[LLMGateway, MockProvider]:
    provider = MockProvider(responses=[LLMResponse(content=r, model="mock-model") for r in responses])
    return LLMGateway(provider, settings), provider
