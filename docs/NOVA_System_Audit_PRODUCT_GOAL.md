# SYSTEM AUDIT — NOVA AI Employee

> Независимый архитектурный аудит против `PRODUCT_GOAL.md`  
> Дата: 2026-07-14

> **Примечание:** файл `NOVA_System_Audit_PRODUCT_GOAL.docx` в этой же папке — Word-копия для скачивания. На GitHub preview бинарника выглядит как «кракозябры» (это нормально). Читайте этот `.md` или скачайте `.docx` и откройте в Word / Google Docs.

## Метаданные аудита

**Роль аудитора:** независимый Principal AI Architect / Staff Software Engineer / внешний технический аудитор

**Источник правды:** docs/PRODUCT_GOAL.md

**Объект:** /workspace, ветка cursor/novanova-employee-port-1eba (база NovaNova + port Phase A)

**Метод:** чтение контракта → полный проход кода → сверка доказательств в файлах

**Позиция:** зелёные тесты и «оно работает» не являются защитой. Нарушение Product Goal = дефект.

**Дата:** 2026-07-14

## Вердикт

Система ближе к AI Employee, чем ранний workflow-стек, но не соответствует Product Goal как закрытому контракту. PRODUCT_GOAL.md §11/§14 помечает P0–Sprint E как DONE и «открытых пунктов нет» — это документальная ложь относительно кода. Текущее состояние: pilot с оговорками, не assistant-grade.

## 1. Архитектурные инварианты

| Инвариант | Статус | Доказательство (кратко) |
| --- | --- | --- |
| Executive — единственный decision owner | Нарушен | ConversationService invents ASK_CLARIFICATION; keyword short-circuits до Executive |
| Planner ничего не решает | Частично | LLM Planner gated; узел всегда на task path; demotion по len(caps)<=1 |
| Context Builder не меняет смысл | Соблюдается | Агрегация + merge transport; decision не выбирает |
| Telegram не принимает решений | Частично | flow.py thin; product-логика в ConversationService; мёртвый continuation |
| Orchestrator не знает бизнес-смысл capability | Нарушен | NON_CRITICAL_CAPABILITIES = имена skills как политика |
| Skills независимы | Частично | Builtin skills не импортируют друг друга; adapter/continuation и Resolver знают имена |
| Renderer один (Render Contract) | Частично | Skills path основной; dual Document*Node ещё в дереве |
| Conversation FSM один | Частично | Один FSM в ConversationService; side-channels invent decision |
| Нет keyword routing | Нарушен | memory capture + client work summary |
| Нет document routing | Частично | Нет ppt-router; pdf→docx remap / document_type merge остаются |
| Learning не влияет на стратегию | Частично | DecisionType не трогает; soft-inject в context без hard filter |
| Research честный | Нарушен (при enable) | mock→completed; Non-critical skip; Mock default когда OFF |
| Semantic Memory честная | Частично | OFF по умолчанию OK; stub embed path при escape hatch |
| Нет silent success | Нарушен | QualityGate→completed после fail; RevisionSkill всегда completed |
| Нет скрытых side channels | Нарушен | keyword paths; invent clarification; coaching conversation_note |

## 2. UX: workflow engine vs AI Assistant

### Ощущается как AI Assistant

- чат RESPOND без задачи

- re-eval Executive на clarification resume

- отделение chat vs task по DecisionType (не по capability name) на пост-артефактном пути

### Ощущается как workflow engine

- Always-on progress bubble на любом EXECUTE (_should_show_progress → True) — против Sprint E

- Approve показывает чек-лист шагов плана (format_approval_message)

- Slash-команды /status /new /cancel как режимные рычаги

- Busy lock «Ещё работаю…»

- Keyword shortcuts («запомни», «что сделано») — разные ответы на один класс intent

- Изобретённые clarify после incomplete skill — пользователь «продолжает пайплайн», а не диалог

## 3. Findings

### F1. ConversationService invents Product Decision ASK_CLARIFICATION

**Severity:** Critical

**Приоритет:** P0

#### Почему это проблема

Слой диалога сам назначает intent="ASK_CLARIFICATION" и переводит FSM в PENDING_CLARIFICATION после неуспешного skill outcome — без нового решения Executive. Это прямая подмена Product Decision.

#### Где находится

- backend/app/conversation/service.py — _deliver_outcome, _ask_clarification_from_incomplete

- Evidence: incomplete/failed → extract_creation_missing_information → invent clarification

#### Почему нарушает Product Goal

§2, §2.2, §3 «Executive — единственный…»; §3.1 «Никакой другой слой не имеет права подменять Product Decision»; Decision Contract.

#### Как должно работать

Incomplete/failed skill → честный failure / retry UX или следующий user turn заново идёт в Executive. Только Executive может выбрать ASK_CLARIFICATION.

#### Минимальное исправление

Удалить _ask_clarification_from_incomplete как decision path. Оставить incomplete delivery. Missing info — в context следующего хода, не как invented DecisionType.

#### Риски исправления

UX «уточните: …» станет менее автоматическим; нужно вернуть clarify только через Executive prompt + incomplete context.

### F2. Keyword side-channel: «запомни…» минует Executive

**Severity:** Critical

**Приоритет:** P0

#### Почему это проблема

Regex/imperative router до classify полностью обслуживает turn и возвращает completed без Product Decision.

#### Где находится

- backend/app/conversation/service.py — _maybe_capture_memory

- backend/app/memory/capture.py — _IMPERATIVE_PATTERN

- Wiring: backend/app/bootstrap/telegram_app.py

#### Почему нарушает Product Goal

§3 Keyword Routing запрещён; §3.1 «не … keyword-ами, regex»; §10 «Не добавлять keyword shortcuts»; §8 «разные ответы… из-за regex».

#### Как должно работать

Сообщение → Executive (RESPOND или capability). Persistence — side effect после решения, не pre-router.

#### Минимальное исправление

Убрать short-circuit. Capture только post-decision / skill hook. Удалить или ограничить detect до non-routing helper.

#### Риски исправления

«Запомни X» начнёт ходить через LLM (latency/cost); нужна калибровка Executive prompt.

### F3. Keyword side-channel: «что сделано по клиенту X»

**Severity:** Critical

**Приоритет:** P0

#### Почему это проблема

Phrase triggers (что сделано, статус по, истори…) решают поведение диалога в обход Executive.

#### Где находится

- backend/app/clients/work_summary.py — _STATUS_TRIGGERS, detect_client_status_query

- backend/app/conversation/service.py — _maybe_client_work_summary

#### Почему нарушает Product Goal

§3 Keyword Routing; §1.1 Conversation/channel не decision owner; §8.

#### Как должно работать

Вопрос о статусе → Executive RESPOND; данные из repos/tools после решения.

#### Минимальное исправление

Удалить pre-Executive short-circuit. Опционально — skill/RESPOND enrichment по hints Resolver, не по regex.

#### Риски исправления

Потеря «быстрого» UX; компенсируется явно через Executive.

### F4. Silent success: QualityGateNode переписывает статус в completed

**Severity:** Critical

**Приоритет:** P0

#### Почему это проблема

После review update всегда ставит status=completed (или waiting_user_revision), игнорируя upstream execution_failed. Создаёт success-shaped outcome.

#### Где находится

- backend/app/quality/nodes/quality_gate_node.py (~status assignment)

- Связанно: backend/app/quality/gate.py — _is_non_document_flow auto-pass EXECUTE без AST

#### Почему нарушает Product Goal

§8 нет silent «Готово»; P0-B status != completed → FAIL; §11.2 P0-B marked DONE — регресс/дыра.

#### Как должно работать

Quality только на successful execution. FAILED остаётся FAILED до delivery.

#### Минимальное исправление

Propagate execution_failed / FAILED; не вызывать soft PASS на failed executor. Добавить regression test.

#### Риски исправления

Больше явных fail в e2e — правильно для честности.

### F5. Silent success: RevisionSkill всегда возвращает completed

**Severity:** Critical

**Приоритет:** P0

#### Почему это проблема

Skill игнорирует RevisionStatus.FAILED / WAITING_USER и всегда отдаёт status=completed.

#### Где находится

- backend/app/skills/builtin/revision_skill.py (return block с фиксированным completed)

#### Почему нарушает Product Goal

P0-B executor honesty; §8; §3 Skills не принимают продуктовых решений ценой лжи о статусе.

#### Как должно работать

Map domain status → skill status: FAILED→failed, WAITING_USER→waiting/incomplete, COMPLETED→completed.

#### Минимальное исправление

Derive status from result.status. Поправить тесты, которые закрепляют always-completed.

#### Риски исправления

Падут «happy-only» tests — ожидаемо.

### F6. Redis user_lock TTL = 30s при classify внутри lock

**Severity:** Critical

**Приоритет:** P0

#### Почему это проблема

LOCK_TTL_SECONDS = 30, а user_lock держит критическую секцию через Executive LLM classify. Lock может истечь → race FSM при multi-worker / медленном LLM.

#### Где находится

- backend/app/conversation/redis_store.py — LOCK_TTL_SECONDS, set(... ex=LOCK_TTL_SECONDS)

- backend/app/conversation/service.py — handle_message → user_lock → _handle_message_locked → _classify_intent

#### Почему нарушает Product Goal

§3 «состояние диалога не process memory как SoT» + P0-D restart/workers>1 safety для clarify/approval/revision.

#### Как должно работать

Lock heartbeat / TTL намного больше classify, или classify вне короткого lock с CAS на save.

#### Минимальное исправление

Renew lock while held; abort save if token lost (сейчас warning без fence).

#### Риски исправления

Сложнее concurrency; без этого FSM integrity фальшива.

### F7. ExecutionStore — process-local singleton как SoT

**Severity:** High

**Приоритет:** P0

#### Почему это проблема

ExecutionStore = in-process dict + lru_cache singleton. Multi-worker / restart ломает API progress / orchestration lookups.

#### Где находится

- backend/app/orchestration/store.py

- Wiring: bootstrap/telegram_app.py, api/deps.py

#### Почему нарушает Product Goal

§3 состояние не process memory SoT; Sprint D multi-worker; §10 формулировка про process memory.

#### Как должно работать

Redis/Postgres ExecutionStore fail-closed в shared deploy, либо явный single-worker contract и отказ multi-replica.

#### Минимальное исправление

Redis-backed store в prod; fail-closed при недоступности.

#### Риски исправления

Миграция API progress clients.

### F8. Telegram idempotency fail-open на ошибке Redis

**Severity:** High

**Приоритет:** P0

#### Почему это проблема

На exception Redis claim возвращает True → duplicate pipeline allowed.

#### Где находится

- backend/app/adapters/telegram/idempotency.py — except ... return True («fail open»)

#### Почему нарушает Product Goal

Sprint D security fail-closed pattern; idempotent updates; риск silent double-execution.

#### Как должно работать

Production: fail-closed (drop/retry), не process update.

#### Минимальное исправление

is_production → return False / raise на Redis error.

#### Риски исправления

Кратковременный drop updates при Redis blip — лучше, чем double spend.

### F9. Coaching conversation_note подсказывает DecisionType

**Severity:** High

**Приоритет:** P1

#### Почему это проблема

В payload вшиты imperative rules: «если clarifying → continue task / если chat → RESPOND / если new deliverable → new task». Это decision logic вне Executive contract.

#### Где находится

- backend/app/conversation/service.py — _build_runtime_payload

#### Почему нарушает Product Goal

§3.1 Context/Conversation не выбирают clarify vs execute; §3.1 запрет подмены decision «эвристиками».

#### Как должно работать

Только structured pending_clarification. Правила DecisionType — только в Executive prompt/contract.

#### Минимальное исправление

Удалить imperative conversation_note; оставить JSON pending.

#### Риски исправления

Временно больше mis-routing, пока Executive prompt не усилен.

### F10. Orchestrator знает бизнес-критичность capability по имени

**Severity:** High

**Приоритет:** P1

#### Почему это проблема

NON_CRITICAL_CAPABILITIES = {research, strategy_analysis, analytics, client_intelligence} → soft-skip research и др. Orchestrator принимает продуктовое значение имён.

#### Где находится

- backend/app/planning/policies/execution_policy.py

- backend/app/orchestration/orchestrator.py — _giveup_is_tolerable

#### Почему нарушает Product Goal

§1.1 / §3 Orchestrator «не знает смысл capability»; §3.1; §6.1 research honesty при soft success без research.

#### Как должно работать

Criticality — метаданные шага/реестра (step.critical: bool), не hardcode имён в Orchestrator.

#### Минимальное исправление

Вынести flag в capability registry / plan step; Orchestrator читает bool.

#### Риски исправления

Research failures станут hard-fail — правильно при включённом research в плане.

### F11. Capability Resolver fail-open в document pipeline

**Severity:** High

**Приоритет:** P1

#### Почему это проблема

DEFAULT_EXECUTE_PIPELINE = (document_creation, document_rendering). Если hints невалидны → fallback на document pipeline вместо fail-closed. Меняет product outcome.

#### Где находится

- backend/app/skills/capability_resolver.py

#### Почему нарушает Product Goal

§3 Resolver «не меняет Decision»; риск превращения любого execute в КП; противоречие fail-closed docstring.

#### Как должно работать

Пустые hints → явная default policy только для unnamed document tasks. Non-empty invalid hints → CapabilityResolutionError.

#### Минимальное исправление

if hint and not valid: raise. Default только при genuinely empty hints.

#### Риски исправления

Больше fail на плохих hints — честнее, чем wrong artifact type.

### F12. Research mock может считаться completed

**Severity:** High

**Приоритет:** P1

#### Почему это проблема

При mock/mock_not_production ResearchSkill всё ещё отдаёт status=completed если есть AST. Также при research_enabled=False bootstrap создаёт ResearchManager с Mock default.

#### Где находится

- backend/app/skills/builtin/research_skill.py

- backend/app/research/manager.py (default Mock)

- backend/app/bootstrap/telegram_app.py, api/deps.py

- Tests lock this: tests/test_research.py

#### Почему нарушает Product Goal

§6.1 / §6.3 off⇒absent; mock не product success; CAPABILITY_MATRIX honesty.

#### Как должно работать

Mock → failed/unavailable вне tests. OFF → NoOp, не Mock. Completed только на real provider.

#### Минимальное исправление

NoOp when disabled; skill fails on mock_not_production; rewrite tests.

#### Риски исправления

Ломаются тесты, закрепляющие wrong semantics — удалить/переписать.

### F13. Checkpoints durable только при APP_ENV=production

**Severity:** High

**Приоритет:** P1

#### Почему это проблема

Staging/pilot multi-worker с APP_ENV=development (как на сервере) → InMemory checkpoints → interrupt/recovery fragile.

#### Где находится

- backend/app/agent_runtime/checkpoint/manager.py — Redis только для production string

#### Почему нарушает Product Goal

P1-A Redis checkpoints; restart-safe; текущий prod-like сервер на APP_ENV=development.

#### Как должно работать

Durable checkpoint когда Redis SoT / shared workers, не только по env-имени.

#### Минимальное исправление

Redis when available + required for multi-worker; fail-closed if required.

#### Риски исправления

Dev local может требовать Redis — приемлемо.

### F14. PlannerNode всегда на task path; demotion по count caps

**Severity:** Medium

**Приоритет:** P2

#### Почему это проблема

После Skill Resolver всегда идёт PlannerNode. LLM gated, но demotion CREATE_PLAN→direct при len(caps)<=1 может отменить multi-stage intent после Resolver collapse.

#### Где находится

- backend/app/agent_runtime/graph/edges.py

- backend/app/planning/nodes/planner_node.py

- backend/app/planning/policies/execution_policy.py — should_invoke_llm_planner

#### Почему нарушает Product Goal

§3 Planner только после CREATE_PLAN when needed; §10 «не ≥N caps / не на всякий случай»; Runtime Invariants demotion policy edge.

#### Как должно работать

Отдельный direct_plan node для EXECUTE; LLM Planner только на CREATE_PLAN с branching/unknown structure.

#### Минимальное исправление

Split nodes; demotion только по явной policy metadata, не len<=1 после fallback.

#### Риски исправления

Graph refactor; регрессии planning tests.

### F15. Always-on progress theater

**Severity:** Medium

**Приоритет:** P2

#### Почему это проблема

_should_show_progress всегда True. Sprint E чеклист помечен DONE («меньше theater на single-step»), код противоречит.

#### Где находится

- backend/app/conversation/service.py — _should_show_progress

#### Почему нарушает Product Goal

§1 / §8 assistant feel; §11.5 Sprint E claim; workflow presence.

#### Как должно работать

Progress для CREATE_PLAN / multi-step; single-step EXECUTE — без ephemeral bubble.

#### Минимальное исправление

Gate on decision/step count after resolve.

#### Риски исправления

Низкие.

### F16. Approval UX показывает checklist плана

**Severity:** Medium

**Приоритет:** P2

#### Почему это проблема

format_approval_message печатает «План: 1. … 2. … Начать выполнение?» — workflow checklist.

#### Где находится

- backend/app/conversation/messages.py — format_approval_message

#### Почему нарушает Product Goal

§1 «не ощущать workflow»; §8 плохо: показывать планы как продукт; §10.

#### Как должно работать

Естественное подтверждение без inventory шагов; план — internal.

#### Минимальное исправление

Убрать listing capabilities/descriptions из user text.

#### Риски исправления

Меньше прозрачности для power users — приемлемо per Goal.

### F17. Latent Telegram continuation выбирает capability по имени

**Severity:** Medium

**Приоритет:** P2

#### Почему это проблема

TelegramGraphContinuation._apply_user_revision делает get_skill_for_capability("document_revision"). Провод в bot/service есть; call path reportedly unused — мёртвая мина.

#### Где находится

- backend/app/adapters/telegram/continuation.py

- Wiring в bot.py / ConversationService._continuation

#### Почему нарушает Product Goal

§3 Telegram не decision; Skills independence; adapter capability branching.

#### Как должно работать

Либо удалить, либо resume Runtime с already-decided plan — без hardcode capability в adapter.

#### Минимальное исправление

Delete dead wiring/path.

#### Риски исправления

Низкие, если действительно unused.

### F18. Orchestrator domain merge keys / document_type remap

**Severity:** Medium

**Приоритет:** P2

#### Почему это проблема

_enrich_payload_from_plan знает document_ast, strategy_result, presentation_plan, document_type→output_format.

#### Где находится

- backend/app/orchestration/orchestrator.py

#### Почему нарушает Product Goal

§3 Orchestrator DAG-only; document routing class.

#### Как должно работать

Opaque dependency_results; consumers by contract.

#### Минимальное исправление

Generic bag; format mapping in render skill.

#### Риски исправления

Регрессии document pipeline wiring.

### F19. Quality layer domain forks (presentation/strategy/document)

**Severity:** Medium

**Приоритет:** P2

#### Почему это проблема

Quality gate ветвится по наличию document_ast / presentation_plan / strategy — знает бизнес-смысл артефактов.

#### Где находится

- backend/app/quality/gate.py — _is_non_document_flow

- backend/app/quality/nodes/quality_gate_node.py — _merge_presentation_quality / _merge_strategy_quality

#### Почему нарушает Product Goal

Слой знает бизнес-смысл артефактов/capabilities (§3).

#### Как должно работать

Per-capability quality hooks в skills; gate — агрегатор.

#### Минимальное исправление

Вынести domain validators из gate.

#### Риски исправления

Рефакторинг quality pipeline.

### F20. Dual / dead execution paths в дереве

**Severity:** Medium

**Приоритет:** P2

#### Почему это проблема

DocumentCreationNode / render nodes / StubQualityChecker живут рядом со skills path; e2e helpers ещё могут wire old graph.

#### Где находится

- backend/app/document_creation/nodes/*

- backend/app/planning/nodes/executor_node.py — StubQualityChecker

- Comment в agent_runtime/runtime.py что nodes not registered — но код остаётся

#### Почему нарушает Product Goal

P1-D single path / Render Contract; мёртвый код как latent regression.

#### Как должно работать

Один skills path; dead modules deleted/quarantined.

#### Минимальное исправление

Удалить или move to _legacy/; e2e only skills.

#### Риски исправления

Нужно проверить, что e2e/helpers не зависят от legacy.

### F21. Learning — soft contract без hard allowlist

**Severity:** Medium

**Приоритет:** P2

#### Почему это проблема

Learning inject в learning_context через Context Builder. Extraction prompt просит preferences, но server-side filter категорий отсутствует. Прямой DecisionType mutation не найден.

#### Где находится

- backend/app/learning/*

- context/builder.py — LearningContextProvider

- learning/policies/learning_policy.py markers

#### Почему нарушает Product Goal

§5 Learning только style/format/language/preferences; не стратегия.

#### Как должно работать

Allowlist categories at write; never inject strategy/routing rules.

#### Минимальное исправление

Hard filter on persist + guard test.

#### Риски исправления

Часть learning rules может отфильтроваться.

### F22. Semantic memory stub path при escape hatch

**Severity:** Medium

**Приоритет:** P2

#### Почему это проблема

При embedding_allow_stub путь stub embed остаётся; OpenRouter embeddings NotImplemented.

#### Где находится

- backend/app/memory/semantic/qdrant_memory.py — stub embed

- embedding_allow_stub config

#### Почему нарушает Product Goal

§6.2 stub vectors ≠ product memory; ADR L4.

#### Как должно работать

OFF until real embeddings; refuse stub вне tests; no stub upserts to shared Qdrant.

#### Минимальное исправление

Refuse stub unless test env; keep default OFF.

#### Риски исправления

Низкие при сохранении OFF.

### F23. PDF/unknown → docx silent remap

**Severity:** Low

**Приоритет:** P3

#### Почему это проблема

Silent coerce unsupported format в docx меняет тип deliverable без честного отказа.

#### Где находится

- backend/app/document_creation/nodes/document_render_node.py (и родственные format branches)

#### Почему нарушает Product Goal

Document Routing class; silent change of deliverable type.

#### Как должно работать

Honest fail «PDF не поддерживается», не silent coerce.

#### Минимальное исправление

Fail closed на unsupported format.

#### Риски исправления

Пользователь чаще увидит отказ — честнее.

### F24. Secrets placeholders не fail-boot в production

**Severity:** Medium

**Приоритет:** P2

#### Почему это проблема

Defaults change-me в config; нет startup assert в main при is_production.

#### Где находится

- backend/app/core/config.py defaults change-me

- Нет startup assert в main при is_production

#### Почему нарушает Product Goal

Production hardening / Production Contract.

#### Как должно работать

Refuse boot если placeholders в prod.

#### Минимальное исправление

Startup validation.

#### Риски исправления

Низкие; правильный fail-fast.

### F25. Документ Product Goal врёт о закрытии gaps

**Severity:** High

**Приоритет:** P0

#### Почему это проблема

§11 отмечает P0-A/B/F, Sprint E как DONE; §14 «Открытых пунктов нет». Код содержит F1–F16. Это создаёт ложную готовность для следующих PR.

#### Где находится

- docs/PRODUCT_GOAL.md §11 progress, §14

#### Почему нарушает Product Goal

Сам документ — источник правды; ложный status ломает auditability (§9 acceptance).

#### Как должно работать

§14 = живой backlog; DONE только с regression tests на инварианты.

#### Минимальное исправление

Reopen §14 с F1–F16; снять ложные DONE с F1/F2/F4/F15.

#### Риски исправления

Нужна дисциплина процесса, не код.

### F26. Тесты закрепляют неправильную архитектуру

**Severity:** Medium

**Приоритет:** P3

#### Почему это проблема

Часть тестов кодирует anti-patterns как желаемое поведение.

#### Где находится

- tests/test_conversation_engine.py — singleton FSM as desired

- tests/test_research.py — mock → completed

- Quality tests без кейса execution_failed survives QualityGate

- (Phase A) тесты keyword routers как feature

#### Почему нарушает Product Goal

§9 — тесты должны защищать Goal, не anti-pattern.

#### Как должно работать

Product tests: Executive ownership; Redis SoT; fail honesty; no keyword decision path.

#### Минимальное исправление

Переписать/удалить locking tests; добавить F1/F2/F4/F5 regressions.

#### Риски исправления

Временно упадёт coverage count — это нормально.

### F27. BusinessClientResolver до classify (context mutation / heuristic)

**Severity:** Medium

**Приоритет:** P2

#### Почему это проблема

До Executive resolver+LLM/heuristic извлекает subject и создаёт client — меняет execution identity до Product Decision. Не invent DecisionType, но влияет на весь последующий контекст/артефакты.

#### Где находится

- backend/app/conversation/service.py — _attach_business_client

- backend/app/clients/resolver.py, name_extractor.py

#### Почему нарушает Product Goal

Дух §3.1 (никакие эвристики не предопределяют product path); риск silent client creation на chat questions.

#### Как должно работать

Attach после EXECUTE/CREATE_PLAN (или по явному Executive hint), не на каждом turn до classify.

#### Минимальное исправление

Вызывать attach только на task decision path после Executive.

#### Риски исправления

Нужно перенести point of attach без потери auto-create на КП.

### F28. Live server APP_ENV=development + TELEGRAM_ALLOW_ALL=true

**Severity:** High

**Приоритет:** P0

#### Почему это проблема

На боевом сервере APP_ENV=development, allow-all — отключает prod gates (checkpoints Redis policy, allowlist deny-all, security fail-closed).

#### Где находится

- Runtime env сервера / .env: APP_ENV, TELEGRAM_ALLOW_ALL

#### Почему нарушает Product Goal

Sprint D ACL; Production Contract; ложная «production readiness».

#### Как должно работать

Pilot/prod: APP_ENV=production, allowlist, fail-closed.

#### Минимальное исправление

Вернуть production flags + allowlist; не держать allow-all постоянно.

#### Риски исправления

Нужно корректно выставить allowlist пользователей.

## 4. Сводка приоритетов

| Priority | Findings |
| --- | --- |
| P0 | F1, F2, F3, F4, F5, F6, F7, F8, F25, F28 |
| P1 | F9, F10, F11, F12, F13 |
| P2 | F14–F22, F24, F27 |
| P3 | F23, F26 |

Critical count: 6 (F1–F6)

High count: 8+ (F7–F13, F25, F28)

## 5. Что уже соответствует Goal (не находки)

- Telegram flow.py как thin DTO→service map (адаптер сам не содержит FSM).

- Context Builder не выбирает DecisionType.

- Builtin skills не импортируют peer skills.

- Post-artifact routing завязан на DecisionType, не на capability-name revision regex.

- Clarification resume (когда путь от Executive) повторно вызывает Executive.

- Research/semantic absent from registry когда flags OFF (с оговоркой hidden Mock wiring).

- /ready различает required vs optional deps.

- Compose/TLS/backup/rollback артефакты в deploy/ существуют.

## 6. Рекомендуемый порядок ремонта

- P0 honesty + ownership: убить keyword side-channels (F2/F3); stop inventing clarify (F1); QualityGate/Revision honesty (F4/F5).

- P0 durability/security: lock heartbeat (F6); Redis ExecutionStore (F7); idempotency fail-closed (F8); prod env flags (F28).

- P0 docs truth: reopen §14 (F25).

- P1: coaching note, orchestrator criticality, resolver fail-closed, research honesty, checkpoints.

- P2+: UX theater, dead paths, learning hard filter, demotion split.

## 7. Итоговая позиция аудитора

Пока P0 не закрыт regression-тестами на Product Goal, статус «Sprint A–E DONE / открытых пунктов нет» недопустим. Работающий код и зелёные тесты не являются доказательством правильной архитектуры.
