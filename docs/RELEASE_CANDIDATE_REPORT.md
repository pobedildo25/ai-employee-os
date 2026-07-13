# Release Candidate Report — AI Employee OS / NOVA

**Version:** Release Candidate (Stage G)  
**Date:** 2026-07-13  
**Scope:** Stabilization only — no new product features  
**Criterion:** Fit for controlled production trial (Telegram + API) after env/Docker gates below

---

## 1. Verdict

| Gate | Status |
|------|--------|
| Full pytest regression | **PASS** — 541 passed, 0 failed (126s) |
| Decision catalog (≥150 scenarios) | **PASS** — 164 scenarios |
| Product stages A–F code paths | **PASS** (covered by regression) |
| Docker Compose YAML (dev/prod) | **CONDITIONAL** — valid when `.env` / `.env.production` exist |
| Live Docker stack smoke | **NOT RUN** — Docker daemon unavailable on validation host |
| Live Telegram E2E against real Bot API | **NOT RUN** — requires token + running stack |

**RC recommendation:** Approve for staging deploy when (1) `.env.production` filled from example, (2) Docker engine up, (3) `/health` + `/ready` green, (4) Telegram smoke with real token.

---

## 2. Regression summary

```
541 passed, 0 failed, 0 skipped
Duration: ~2m 06s
Warnings: ~50 (mostly datetime.utcnow deprecations; non-blocking)
```

### Suites included

| Area | Tests (representative) |
|------|------------------------|
| Executive / Decision | `test_executive_*`, `test_executive_decision_scenarios` (164) |
| Planner / Orchestrator | `test_planning`, `test_orchestration`, `test_planner_orchestration_minimization` |
| Conversation | `test_conversation_engine` |
| Telegram UX | `test_telegram_*`, `e2e/test_scenario_05_telegram` |
| Runtime hardening | `test_runtime_hardening`, `test_qdrant_memory`, `test_context_builder` |
| Product behaviour | `test_product_behaviour_ux` |
| Documents / Renderer / Presentation | `test_document_*`, `test_presentation_design`, e2e 01/07 |
| Research / Strategy / Analytics | `test_research`, `test_strategy`, `test_analytics` |
| Learning / Knowledge / Memory | `test_learning`, `test_knowledge`, `test_memory_system` |
| Observability / Security / Health | `test_observability`, `test_security`, `test_health_*`, e2e health |
| Failures | `e2e/test_scenario_06_failures` |

### Stabilization fixes applied in Stage G (tests only)

Aligned outdated assertions with Stages B–F behaviour (no product feature changes):

1. Stream events include `_bootstrap` → `test_runtime_stream_workflow`
2. Telegram product flow requires Executive for task path → adapter/e2e failure tests wire task executive
3. Friendly errors edit progress bubble → failure assertions read `edited` payload

---

## 3. Subsystem production validation matrix

| Subsystem | Unit/Integration | Hardening / degrade | Prod notes |
|-----------|------------------|---------------------|------------|
| **Docker** | Dockerfile + compose present | Entrypoint runs Alembic when `RUN_MIGRATIONS_ON_STARTUP=true` | Need `.env` / `.env.production`; daemon must be running for smoke |
| **PostgreSQL** | health checks, workspace, knowledge, learning stores | Required for sessions | Pool settings in prod example |
| **Redis** | memory short-term, health | Degrade via MemoryManager isolation | AOF enabled in compose |
| **Qdrant** | semantic memory tests | Lazy init + in-memory fallback | Optional for task success |
| **MinIO** | storage / artifacts | Upload degrade keeps render bytes | Health in `/ready` |
| **Telegram** | product UX, chat vs task, e2e scenario 05 | UI errors ≠ abort execution; thin transport | Needs `TELEGRAM_BOT_TOKEN`; workers=1 in prod example |
| **Learning** | extractor / manager / e2e 03 | LLM outage → `should_learn=False` | Keyword markers remain for preference detection |
| **Knowledge** | store / context provider | Context builder soft-fail | Postgres-backed |
| **Research** | researcher + mock provider | Provider/LLM → heuristic fallback | Mock web provider — not live browsing |
| **Strategy** | strategy skill/node | Via EXECUTE path | Covered in e2e 02 |
| **Analytics** | analyzer + data provider | LLM/repo degrade | — |
| **Presentation** | presentation_design | Via skills registry | — |
| **Documents** | creation / intelligence | Quality + revision loops | e2e 01 |
| **Renderer** | docx/pptx/pdf | Soft fail on crash; storage optional | — |
| **Memory** | short/long/semantic | Per-store isolation | Feature flag `MEMORY_ENABLED` |
| **Executive Agent** | decision scenarios + agent | OpenRouter outage → degraded RESPOND | Core dependency for quality replies |
| **Planner** | CREATE_PLAN ≥2 caps only | Demote single-cap; approval only multi-step | — |
| **Conversation** | session singleton, history, clarification | RESPOND keeps revision context | — |
| **Observability** | traces / logging | Health liveness vs readiness | `/health`, `/ready`, `/api/v1/*` |
| **Security** | API keys, rate limit | Enabled in prod example | Set strong `APP_SECRET_KEY` |

---

## 4. Stages A–F product contract (frozen for RC)

| Stage | Outcome |
|-------|---------|
| A Executive Decision | RESPOND-first; no keyword routing; EXECUTE vs CREATE_PLAN |
| B Conversation | Persistent Telegram store/session; history; clarification |
| C Planner/Orchestrator | Planner only multi-cap; skip graph for 1 step |
| D Telegram UX | Ephemeral progress; fewer bubbles; no Quality score in chat |
| E Runtime Hardening | External services degrade; UI ≠ abort |
| F Product Behaviour | ≥150 scenarios; draft-first; revision vs new task |

---

## 5. Smoke checklist (operator)

Run after `cp .env.example .env` (or prod example → `.env.production`) and Docker Desktop start:

```bash
# Dev
docker compose up -d --build
curl -f http://localhost:8000/health
curl -f http://localhost:8000/ready

# Prod
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
curl -f http://localhost:8000/health
curl -f http://localhost:8000/ready
```

Telegram smoke (manual):

1. `/start` or «Привет» → single chat reply, no «Думаю…»
2. «Что такое SWOT?» → RESPOND, no plan
3. «Сделай КП» → draft EXECUTE path (progress → result), not dead-end clarify-only
4. Multi-stage plan (≥2 dependent caps) → approval only if multi-step
5. After document: «Сделай короче» → revision; «Сделай SWOT для Aurora» → new task
6. Kill Qdrant briefly → task still completes (degraded memory)

---

## 6. Known limitations (accepted for RC)

1. **Research/news** — no live web browsing; RESPOND must stay honest about stale/no real-time data  
2. **Embeddings** — stub vectors in Qdrant semantic memory  
3. **Docker smoke on CI host** — not executed here (daemon down)  
4. **Real OpenRouter / Telegram** — not exercised in automated suite (mocked)  
5. **Deprecation warnings** — `datetime.utcnow()` cleanup deferred (non-blocking)

---

## 7. Release blockers vs non-blockers

### Blockers before production traffic

- [ ] Create `.env.production` from `.env.production.example` with real secrets  
- [ ] Set `AGENCY_ARCHIVE_PATH` to existing host path  
- [ ] `OPENROUTER_API_KEY` and `TELEGRAM_BOT_TOKEN` configured  
- [ ] Stack healthy: `/ready` shows postgres/redis/qdrant/minio up  
- [ ] Manual Telegram smoke (section 5) passed on staging  

### Non-blockers

- Qdrant/MinIO temporary outage (degraded mode)  
- Pytest deprecation warnings  
- Mock research provider  

---

## 8. Sign-off

| Role | Result |
|------|--------|
| Automated regression | **PASS (541)** |
| Product behaviour catalog | **PASS (164 scenarios)** |
| Infra compose templates | **PASS (examples present)** |
| Live production stack validation | **PENDING (operator env)** |

**RC status:** Codebase is Release Candidate ready for staging. Production go-live requires operator checklist in §5–§7.
