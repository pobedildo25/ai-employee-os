import json

CLIENT_INTELLIGENCE_SYSTEM_PROMPT = """You are a Client Intelligence analyzer for AI Employee OS.
Aggregate patterns from existing memory/knowledge/learning/workspace notes.
Return ONLY valid JSON.
Do NOT invent CRM facts. Prefer low confidence when evidence is thin.
Output signals the system already observed — preferences, communication, risks.
"""


def build_analyzer_user_message(*, client_id: str, evidence: list[str], hints: dict) -> str:
    payload = {
        "client_id": client_id,
        "evidence": evidence[:40],
        "hints": hints,
        "response_schema": {
            "summary": "string",
            "industry": "string|null",
            "services": ["string"],
            "signals": [
                {
                    "category": "preference|communication|history|risk",
                    "key": "string",
                    "value": "string",
                    "confidence": 0.0,
                }
            ],
            "recommendations": ["string"],
            "risks": ["string"],
            "confidence": 0.0,
        },
    }
    return (
        "Analyze client intelligence evidence and return JSON.\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
