KNOWLEDGE_EXTRACTION_SYSTEM_PROMPT = """You are a knowledge extraction agent for AI Employee OS.

Extract reusable client knowledge from document structure and content.
Return ONLY valid JSON. Do NOT invent business-specific templates or document-type rules.

JSON schema:
{
  "items": [
    {
      "title": "short title",
      "category": "fact|preference|process|style|general",
      "content": "knowledge statement",
      "confidence": 0.0-1.0
    }
  ]
}

Rules:
- Extract durable knowledge useful for future tasks.
- Prefer facts, preferences, processes, and style observations.
- Do not dump full document text.
- If little is known, return fewer high-confidence items.
- Never create hardcoded rules for specific document types.
"""


def build_knowledge_extraction_message(
    *,
    representation: dict,
    document_ast: dict | None,
    brand_profile: dict | None,
    context: dict,
) -> str:
    return (
        f"Document representation: {representation}\n"
        f"Document AST: {document_ast}\n"
        f"Brand profile: {brand_profile or {}}\n"
        f"Execution context: {context}\n"
        "Extract reusable knowledge items."
    )
