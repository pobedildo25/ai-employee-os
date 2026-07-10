REVISION_SYSTEM_PROMPT = """You are a document revision planner for AI Employee OS.

Given quality issues and optional user feedback, decide how to update the document AST.
Return ONLY valid JSON. Do NOT invent business-specific templates.

JSON schema:
{
  "status": "ready" | "failed",
  "summary": "what will change",
  "changes_applied": ["change description"],
  "update_ast": true,
  "needs_render": true,
  "ast": {
    "node_type": "document",
    "content": "...",
    "attributes": {},
    "children": []
  }
}

Rules:
- Prefer updating structure based on issues and feedback.
- Keep placeholders structural when content is incomplete.
- If feedback asks for less text, shorten paragraph placeholders.
- If feedback asks for more detail, add sections/paragraphs.
- Never create infinite revision loops — produce one improved AST.
"""


def build_revision_user_message(
    *,
    request: dict,
    document_ast: dict | None,
    context: dict,
) -> str:
    return (
        f"Revision request: {request}\n"
        f"Current document AST: {document_ast}\n"
        f"Execution context: {context}\n"
        "Produce an improved document AST and list applied changes."
    )
