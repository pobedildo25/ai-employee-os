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


def creation_ast_json(
    *,
    status: str = "ready",
    document_type: str = "docx",
    title: str = "Client Document",
    missing_information: list[str] | None = None,
) -> str:
    if status == "incomplete":
        payload = {
            "status": "incomplete",
            "document_type": document_type,
            "missing_information": missing_information or ["нет данных клиента"],
            "metadata": {"title": title},
            "ast": None,
        }
        return json.dumps(payload, ensure_ascii=False)

    payload = {
        "status": "ready",
        "document_type": document_type,
        "missing_information": [],
        "metadata": {"title": title, "summary": "Universal document structure"},
        "ast": {
            "node_type": "document",
            "content": title,
            "attributes": {},
            "children": [
                {
                    "node_type": "section",
                    "content": "Introduction",
                    "attributes": {},
                    "children": [
                        {
                            "node_type": "heading",
                            "content": "Overview",
                            "attributes": {},
                            "children": [],
                        },
                        {
                            "node_type": "paragraph",
                            "content": "[Client overview section]",
                            "attributes": {},
                            "children": [],
                        },
                    ],
                },
                {
                    "node_type": "section",
                    "content": "Details",
                    "attributes": {},
                    "children": [
                        {
                            "node_type": "heading",
                            "content": "Services",
                            "attributes": {},
                            "children": [],
                        },
                        {
                            "node_type": "paragraph",
                            "content": "[Services description section]",
                            "attributes": {},
                            "children": [],
                        },
                    ],
                },
            ],
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def review_json(
    *,
    status: str = "PASS",
    score: float = 0.9,
    summary: str = "Result meets the user goal",
    issues: list[dict] | None = None,
    recommendations: list[str] | None = None,
) -> str:
    payload = {
        "status": status,
        "score": score,
        "summary": summary,
        "issues": issues or [],
        "recommendations": recommendations or [],
        "metadata": {},
    }
    return json.dumps(payload, ensure_ascii=False)


def knowledge_json(
    *,
    items: list[dict] | None = None,
) -> str:
    payload = {
        "items": items
        or [
            {
                "title": "Client tone",
                "category": "preference",
                "content": "Client prefers concise formal language",
                "confidence": 0.8,
            },
            {
                "title": "Service focus",
                "category": "fact",
                "content": "Primary offering is digital marketing services",
                "confidence": 0.75,
            },
        ]
    }
    return json.dumps(payload, ensure_ascii=False)


def revision_json(
    *,
    status: str = "ready",
    summary: str = "Applied quality feedback",
    changes: list[str] | None = None,
    title: str = "Revised Document",
) -> str:
    payload = {
        "status": status,
        "summary": summary,
        "changes_applied": changes or ["Updated structure based on review feedback"],
        "update_ast": True,
        "needs_render": True,
        "ast": {
            "node_type": "document",
            "content": title,
            "attributes": {},
            "children": [
                {
                    "node_type": "section",
                    "content": "Revised Section",
                    "attributes": {},
                    "children": [
                        {
                            "node_type": "heading",
                            "content": "Improved Overview",
                            "attributes": {},
                            "children": [],
                        },
                        {
                            "node_type": "paragraph",
                            "content": "[Revised content placeholder]",
                            "attributes": {},
                            "children": [],
                        },
                    ],
                }
            ],
        },
    }
    return json.dumps(payload, ensure_ascii=False)
