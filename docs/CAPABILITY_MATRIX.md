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
| research | **off** | `research_enabled=False` | Not registered when flag off |
| document_rendering | prod / PDF stub | `skills_enabled` | DOCX/PPTX real; PDF renderer stub |
| quality_review | prod | `skills_enabled` | Real skill |
| revision | prod | `skills_enabled` | Real skill |
| knowledge_migration | prod | `skills_enabled` | Real skill |
| DocumentSkill / AnalysisSkill / FileSkill | **stub** | — | Not in prod registry |
| semantic memory | **off** | `semantic_memory_enabled=False` | Not a skill; product surface off |

Default flags: `skills_enabled=True`, `research_enabled=False`, `semantic_memory_enabled=False`.
