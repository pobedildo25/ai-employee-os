# Capability Matrix — NOVA

Aligned with `create_capability_registry` (`backend/app/skills/registry.py`).

Rule: **off ⇒ absent from registry and from prompts.**

| Capability / skill | Status | Flag | Notes |
|--------------------|--------|------|-------|
| document_analysis | prod | `skills_enabled` | Real skill |
| brand_style_analysis | prod | `skills_enabled` | Real skill |
| document_creation | prod | `skills_enabled` | Real skill |
| presentation_design | prod | `skills_enabled` | Real skill |
| strategy | prod | `skills_enabled` | Real skill |
| client_intelligence | prod | `skills_enabled` | Real skill |
| analytics | prod | `skills_enabled` | Real skill |
| research | **sonar-ready / off by default** | `research_enabled` + `research_provider=sonar` | Perplexity Sonar via OpenRouter; Mock only with `research_allow_mock` |
| document_rendering | prod / PDF stub | `skills_enabled` | DOCX/PPTX real; PDF renderer stub |
| quality_review | prod | `skills_enabled` | Real skill |
| revision | prod | `skills_enabled` | Real skill |
| knowledge_migration | prod | `skills_enabled` | Real skill |
| DocumentSkill / AnalysisSkill / FileSkill | **removed** | — | Stub modules deleted (L1); not in tree |
| semantic memory | **off** | `semantic_memory_enabled=False` | Not a skill; enable only per `ADR_RESEARCH_EMBEDDINGS.md` |

Default flags: `skills_enabled=True`, `research_enabled=False`, `semantic_memory_enabled=False`.
