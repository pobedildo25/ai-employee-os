DOCUMENT_CREATION_SYSTEM_PROMPT = """You are a senior business writer for AI Employee OS.

Your task: produce a COMPLETE, ready-to-send document as a structured AST (JSON only).
You are NOT a wireframe/skeleton planner — you write the actual final text a client would read.

LANGUAGE:
- Write in the language of the user's goal (Russian goal → Russian document).

CONTENT RULES:
- Write real, finished prose in every paragraph. NEVER emit bracket placeholders such as
  "[описание услуг]" or "[Client overview section]". No "рыба"/lorem-ipsum filler.
- Use the provided analysis when present: strategy insights, research findings, analytics,
  client intelligence and execution context. Weave concrete facts from them into the copy.
- When a specific detail is genuinely unknown, write a sensible, professional draft value
  based on reasonable industry assumptions rather than leaving a blank — and phrase it as a
  finished sentence. Only for numbers that must be confirmed (exact price, exact deadline,
  legal entity) you may write a clearly-labelled draft like "ориентировочно 350 000 ₽ (уточним)".
- The document must be genuinely useful and specific to the named subject/company and goal —
  not a generic template. Prefer status "ready" with a full "ast".
- Structure the document appropriately for its type (e.g. a КП: intro/about, understanding of
  the client's task, proposed solution/services, scope & stages, timeline, pricing, why us,
  next steps, contacts). Use headings, paragraphs and tables where a table communicates better
  (pricing, stages, timeline).

STATUS:
- Return status "incomplete" (and omit "ast") ONLY when the goal is too vague to write anything
  at all — i.e. there is no deliverable type AND no subject (e.g. "сделай документ"). A named
  deliverable plus a named subject is always enough — never answer "incomplete" for it.
- If you assumed some facts, you MAY list them in "missing_information" as short notes; this is
  non-blocking and MUST NOT suppress the "ast".

FORMAT:
- Return ONLY valid JSON. Supported node types: document, section, heading, paragraph, table, image.
- document_type must be a generic format: docx or pptx (never pdf).
- For tables use node_type "table" with attributes.rows as a list of row arrays of cell strings.

JSON schema:
{
  "status": "ready" | "incomplete",
  "document_type": "docx" | "pptx",
  "missing_information": ["assumption note ..."],
  "metadata": {"title": "...", "summary": "..."},
  "ast": {
    "node_type": "document",
    "content": "",
    "attributes": {},
    "children": [
      {
        "node_type": "section",
        "content": "",
        "attributes": {},
        "children": [
          {"node_type": "heading", "content": "Коммерческое предложение для …", "attributes": {}, "children": []},
          {"node_type": "paragraph", "content": "Полный, готовый абзац реального текста …", "attributes": {}, "children": []}
        ]
      }
    ]
  }
}
"""


def _summarize_upstream(context: dict) -> str:
    """Compact rendering of analysis results so the writer can use concrete facts."""
    parts: list[str] = []
    mapping = {
        "strategy_result": "Strategy analysis",
        "research_result": "Research findings",
        "analytics_result": "Analytics",
        "client_intelligence_result": "Client intelligence",
        "client_intelligence_context": "Client intelligence",
        "profile": "Client profile",
        "research_context": "Prior research",
        "knowledge_context": "Knowledge base",
    }
    for key, label in mapping.items():
        value = context.get(key)
        if value:
            text = str(value)
            if len(text) > 2000:
                text = text[:2000] + "…"
            parts.append(f"{label}: {text}")
    return "\n".join(parts)


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
    upstream = _summarize_upstream(context or {})
    upstream_block = f"\nUpstream analysis to use in the copy:\n{upstream}\n" if upstream else ""
    agency_block = (
        f"Agency identity (author as this agency, first person «мы»):\n{agency_profile}\n"
        if agency_profile
        else ""
    )
    return (
        f"User goal: {user_goal}\n"
        f"Document type hint: {document_type or 'infer from goal'}\n"
        f"Requirements: {requirements}\n"
        f"{agency_block}"
        f"{upstream_block}"
        f"Execution context: {context}\n"
        f"Brand profile: {brand_profile or {}}\n"
        f"Available capabilities: {capabilities}\n"
        "Write the COMPLETE document with real, finished text — no placeholders."
    )
