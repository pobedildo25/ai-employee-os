# Production Contract — NOVA

What the product **guarantees** in production / pilot surface, and what it **does not**.

## Guarantees

- Product Decision only via Executive: `RESPOND` | `ASK_CLARIFICATION` | `EXECUTE` | `CREATE_PLAN`.
- Telegram is transport only; dialog FSM lives in ConversationService.
- Research capability is **off** (`research_enabled=False`) — absent from registry and prompts.
- Semantic memory is **off** (`semantic_memory_enabled=False`) — not in product surface.
- Stub skills (`DocumentSkill` / `AnalysisSkill` / `FileSkill`) are **not** registered in production.
- Silent «Готово» without a real result is forbidden.
- Production security store and rate limiter require Redis (no silent InMemory fallback).
- Empty Telegram allowlist in production → deny all users.

## Explicitly not guaranteed / not offered

| Area | Status | Notes |
|------|--------|-------|
| Live news / real-time web | **Not supported** | Honest RESPOND; no mock browsing |
| Research capability | **OFF** | Flag off; no mock research in product surface |
| Semantic memory / embeddings | **OFF** | Flag off until stack + cost decision |
| PDF rendering | **Stub** | `PdfRenderer` raises; do not offer PDF as ready |
| LangGraph checkpoint Redis | **Not required** | Approval resumes from stored plan/decision |
| Keyword / document routing | **Forbidden** | Never use as decision path |

## Banned in product surface

- Mock / stub research presented as real answers.
- Fake «live» data when no live source exists.
- InMemory security / rate-limit as production source of truth.
- Accepting all Telegram users when allowlist is empty in production.
