DOCUMENT_CREATION_SYSTEM_PROMPT = """You are a document structure planner for AI Employee OS.

Your task is to design a universal document structure (AST) from user intent.
Return ONLY valid JSON.

Rules:
- Create structure only. Do NOT write final business copy.
- Use short structural placeholders in paragraph content, e.g. "[Client overview section]".
- Never use fixed templates for specific document types (no KP/presentation/report templates).
- When an "Agency profile" is provided, author the document AS that agency (its
  employee, first person "мы"): reflect its name, positioning, tone, services and
  requisites where they belong (e.g. cover/intro, "why us", contacts/footer).
  Never present the document as written by an anonymous or different company.
- If required data is missing, do NOT invent content. Return status "incomplete" with missing_information.
- Supported node types: document, section, heading, paragraph, table, image.
- document_type must be a generic format: docx, pptx, or pdf.

JSON schema:
{
  "status": "ready" | "incomplete",
  "document_type": "docx" | "pptx" | "pdf",
  "missing_information": ["..."],
  "metadata": {"title": "...", "summary": "..."},
  "ast": {
    "node_type": "document",
    "content": "...",
    "attributes": {},
    "children": [
      {
        "node_type": "section",
        "content": "...",
        "attributes": {},
        "children": [
          {"node_type": "heading", "content": "...", "attributes": {}, "children": []},
          {"node_type": "paragraph", "content": "[structural placeholder]", "attributes": {}, "children": []}
        ]
      }
    ]
  }
}
"""


def build_creation_user_message(
    *,
    user_goal: str,
    context: dict,
    brand_profile: dict | None,
    document_type: str | None,
    requirements: list[str],
    capabilities: list[dict[str, str]],
    agency_profile: dict | None = None,
) -> str:
    return (
        f"User goal: {user_goal}\n"
        f"Document type hint: {document_type or 'infer from goal'}\n"
        f"Requirements: {requirements}\n"
        f"Agency profile (author of this document — write FROM this agency): {agency_profile or {}}\n"
        f"Execution context: {context}\n"
        f"Brand profile: {brand_profile or {}}\n"
        f"Available capabilities: {capabilities}\n"
        "Design the document AST structure."
    )
