# Product Goal — NOVA

**Статус:** источник правды для продукта, архитектуры и плана исправлений.  
Любой PR, который нарушает этот документ, отклоняется — даже при зелёных тестах.

**Прогресс (2026-07-13):** Sprint A — **PARTIAL** (`1edbb65` + leftovers in this PR: P0-G fail-closed Redis/allowlist, P0-B missing `status` → FAIL, Stage 0 contracts). Sprint B — **PARTIAL**: P0-D/P0-E DONE; P0-C DONE (ConversationService channel-neutral via ports; Telegram = adapter; Redis FSM field aliases `telegram_*` retained). Sprint C — **PARTIAL** (Resolver owns ordered graph from hints + fail-closed; unified Render Contract entry; PDF not offered / stub; history truncate; Redis app-level checkpoint; LangGraph interrupt checkpointer still MemorySaver; live LLM eval open). Sprint D — **PARTIAL** (landed: Redis AUTH, Qdrant key, MinIO pin, migration lock, Telegram worker, tenant ACL, Sentry/metrics, readiness; open: TLS / backups schedule / rollback playbook / Celery; Redis security+rate-limit InMemory fallback fixed as Sprint A/P0-G leftover this PR).

---

## 1. Что мы строим

**NOVA — это не workflow engine.**  
**NOVA — это универсальный AI Employee.**

Имя ассистента: **NOVA**.  
Продукт: единый интеллектуальный сотрудник маркетингового агентства, а не набор отдельных ботов.

Основной интерфейс — Telegram. Telegram — транспорт, не мозг системы.

Пользователь должен ощущать взаимодействие так же естественно, как с **ChatGPT**, **Claude** или **Gemini**.

Workflow, planner, orchestration, revision, quality gate и память — **внутренние механизмы**.  
Они не должны ощущаться пользователем как отдельные режимы, «движок», чеклисты или инженерный процесс.

### 1.1 Разделение ответственности (кратко)

| Компонент | Делает | Не делает |
|-----------|--------|-----------|
| **Executive** | Принимает Product Decision | Не строит capability pipeline, не планирует шаги |
| **Capability Resolver** | После `EXECUTE` строит capability graph | Не меняет Product Decision |
| **Planner** | Исполняет решение `CREATE_PLAN` (строит план) | Не роутит intent, не принимает Product Decision |
| **Context Builder** | Агрегирует контекст | Не принимает решения, не меняет смысл запроса |
| **Telegram / каналы** | Транспорт и UI | Не принимают решения |
| **Skills** | Выполняют свою capability | Не знают друг друга и продукт |
| **Orchestrator** | Координирует DAG исполнения | Не принимает решения, не знает смысл capability |
| **Runtime** | Исполняет уже принятое решение | Не принимает Product Decision |

---

## 2. Продуктовые правила поведения

| Ситуация | Ожидание |
|----------|----------|
| Простые вопросы | Мгновенный текстовый ответ |
| Консультации и анализ «в чате» | Текстовый ответ, без запуска задачи и плана |
| Простые задачи (создание артефакта) | Выполнение без лишних подтверждений |
| Сложные многоэтапные задачи | Планирование запускается автоматически, **только когда это действительно необходимо** |

Любое **Product Decision** принимает **только Executive Agent**.  
Любой другой компонент может **только исполнять** это решение.

### 2.1 Различение намерений (обязательно)

Executive должен различать:

| Намерение пользователя | Product Decision |
|------------------------|------------------|
| Вопрос | ответ (`RESPOND`) |
| Консультация | ответ (`RESPOND`) |
| Анализ / объяснение | ответ (`RESPOND`) |
| Создание артефакта | задача (`EXECUTE`) |
| Сложная многоэтапная работа | план (`CREATE_PLAN`) |

Planner **не должен** запускаться, если пользователь ожидает обычный диалог.

После уточнения система должна продолжать разговор естественно и **заново оценивать намерение** через Executive — а не автоматически переходить в execution без повторной оценки.

Это устраняет дефект, наблюдаемый на реальном боте (например: «какой курс доллара», «сделай КП», «КП на AI автоматизацию»), когда ChatGPT-подобное ожидание сталкивается с workflow-поведением.

### 2.2 Executive принимает только Product Decision

Executive выбирает **только** Product Decision:

`RESPOND` | `ASK_CLARIFICATION` | `EXECUTE` | `CREATE_PLAN`

После `EXECUTE` **Capability Resolver** самостоятельно строит capability graph / pipeline.

**Executive не знает внутреннюю структуру capability pipeline** и не должен выбирать «какие skills в каком порядке».  
Иначе разработчик снова впихнет половину Planner внутрь Executive.

---

## 3. Архитектурные инварианты

Эти правила **не обсуждаются** и не обходятся «для удобства» или «для надёжности».

| Компонент / правило | Роль |
|---------------------|------|
| **Executive** | Единственный, кто принимает Product Decision |
| **Capability Resolver** | Строит capability graph после `EXECUTE`; не меняет Decision |
| **Planner** | Не принимает решения; не является Intent Router |
| **Context Builder** | Не принимает решения; не меняет смысл запроса |
| **Orchestrator** | Знает только DAG исполнения и зависимости шагов |
| **Runtime** | Исполняет решение Executive; не принимает Product Decision |
| **Telegram / любой канал** | Не принимает решения |
| **Skills** | Ничего не знают друг о друге |
| **Render Contract** | Единый контракт входа на рендер |
| **Conversation FSM** | Один |
| **Keyword Routing** | Запрещён |
| **Document Routing** | Запрещён |

### 3.1 Расшифровка

**Executive**  
Принимает только Product Decision (`RESPOND` / `ASK_CLARIFICATION` / `EXECUTE` / `CREATE_PLAN`).  
Не строит capability pipeline. Не выбирает внутренние skills и их порядок.  
Никакой другой слой не имеет права подменять Product Decision keyword-ами, regex, document-type или «эвристиками ради стабильности».

**Capability Resolver**  
После `EXECUTE` строит capability graph. Не меняет DecisionType. Не подменяет `EXECUTE` на `CREATE_PLAN` и наоборот.

**Planner**  
Строит план **только** после Product Decision `CREATE_PLAN`, и только когда планирование действительно нужно.  
**Не** является Intent Router. Не выбирает, нужна ли задача пользователю. Не роутит по тексту. Не запускается для обычного диалога.

**Когда нужен Planner (критерий)**  
Planner нужен, когда есть:

- зависимости между этапами;
- ветвление;
- или пользователь просит объективно сложную многоэтапную работу.

**Количество capabilities само по себе не является критерием.**

Пример:

```
«Создай КП»
  → линейная цепочка из нескольких skills
  → Planner не нужен
```

Линейный pipeline после `EXECUTE` — это Capability Resolver + исполнение, не Planner.

**Context Builder**  
Только агрегирует контекст (включая merge transport context с собранным).  
**Никогда не изменяет смысл пользовательского запроса.**  
Не выбирает action, capability, revision vs new task, clarify vs execute.  
**Не имеет права удалять transport context**, если это не часть явной политики усечения (truncation).  
Именно потеря transport context ломает pending clarification и другие dialog hints.

**Orchestrator**  
Знает **только DAG исполнения**.  
Может знать зависимости между шагами и статусы.  
Не знает, что означает capability в бизнес-смысле.  
Не принимает Product Decision.  
Не содержит ветвлений вида «если presentation → pptx».

**Telegram и любой другой канал**  
Транспорт и UI (отправка, edit, файлы, кнопки). Не содержит product decision-логики.  
Любой новый канал (Telegram, API Chat, Slack, Web) должен использовать **один и тот же ConversationService** без дублирования логики диалога.

**Skills**  
Независимые возможности. Не импортируют друг друга для роутинга, не ветвятся по чужим capability-именам, не принимают продуктовых решений.  
**Skill не должен знать, какая Skill будет вызвана после него.**  
Skill не знает продукт и не выбирает следующий шаг.

**Render Contract**  
Единый контракт входа на рендер.  
Не обязательно один класс `Renderer`: `DocxRenderer` / `PptxRenderer` / `PdfRenderer` допустимы.  
Важно: **один вход** (единый contract / port), а не разные продуктовые ветки рендера.

**Conversation FSM**  
Один application-level FSM диалога (clarify / running / approval / revision / completed).  
Адаптеры только вызывают его, не плодят свои.

**Вынос Conversation FSM — границы рефакторинга**  
Переносится только orchestration пользовательского диалога в application layer (`ConversationService`).  
**Не переписывать Runtime. Не переписывать LangGraph.**  
Иначе разработчик начнёт рефакторить половину системы без необходимости.

**Состояние диалога**  
Нельзя использовать process memory как **источник истины**.  
Локальный кэш допустим, если он не является единственным хранилищем состояния.

**Keyword Routing — запрещён**  
Нельзя решать поведение по словам пользователя (`сделай`, `короче`, `переделай`, маркеры learning и т.п.) в обход Executive.

**Document Routing — запрещён**  
Нельзя роутить по `document_type`, расширению файла или «это презентация → особая ветка» вне решения Executive и независимых skills.

---

## 4. Runtime Invariants

Runtime **не имеет права** принимать Product Decision.

Runtime выполняет **только** то, что уже решил Executive.

Runtime **не имеет права**:

- менять `DecisionType`;
- запускать Planner самостоятельно;
- выбирать capability / строить capability pipeline вместо Capability Resolver;
- превращать Revision в New Task;
- превращать New Task в Revision;
- превращать `RESPOND` в `EXECUTE`;
- превращать `EXECUTE` в `CREATE_PLAN`;
- превращать `CREATE_PLAN` в `EXECUTE` без явной политики demotion, утверждённой как исполнение уже принятого `CREATE_PLAN` (не как новый Product Decision).

Именно Runtime чаще всего начинает «умнеть» спустя несколько месяцев разработки.  
Любое такое «умнение» — нарушение Product Goal.

---

## 5. Learning

Learning влияет **только** на:

- стиль;
- формат;
- язык;
- оформление;
- пользовательские предпочтения.

Learning **не должен** менять стратегию выполнения задач (какие capabilities вызывать, нужен ли plan, как роутить намерение).

**Learning никогда не влияет на DecisionType Executive.**

---

## 6. Research, Semantic Memory и Feature Flags

### 6.1 Research

Пока не выбран постоянный стек веб-поиска (Perplexity, Tavily, Exa, SerpAPI и т.д.):

- **не** подключать «первый попавшийся» real provider ради галочки;
- capability research — **feature flag OFF**;
- **запрещено** отдавать фиктивные / mock-результаты как успешный research.

### 6.2 Semantic Memory / Embeddings

Embeddings — отдельная архитектурная задача.

Пока не выбран постоянный провайдер embeddings и не оценена стоимость:

- **не** внедрять embeddings «на скорую руку»;
- semantic memory — **feature flag OFF**;
- stub-векторы недопустимы как «работающая память» в product surface.

### 6.3 Правило Feature Flags

Если capability выключена Feature Flag, она **не должна присутствовать**:

- ни в Prompt Executive;
- ни в Capability Registry (как доступная для resolve / execute).

Иначе Executive / Resolver продолжат выбирать или запускать отключённую функцию.

---

## 7. Readiness

Readiness определяется **обязательными** сервисами (например Postgres; Redis — если он источник истины для FSM).

Необязательные сервисы (например Qdrant, MinIO) переводят систему в **DEGRADED**, а не в **NOT READY**.

`/ready` не должен валить весь продукт из-за падения optional dependency, если core path ещё работает.

---

## 8. Как это должно ощущаться для пользователя

### Хорошо

- «Привет» / «Что такое SWOT?» / «Какой курс доллара?» → сразу полезный ответ (с честным disclaimer, если нет live-данных).
- «Напиши письмо клиенту» / «Сделай КП» → черновик без лишних вопросов и без «согласуйте план»; линейный skill pipeline без Planner.
- Уточнение по КП → естественный диалог; execution только после повторной оценки намерения Executive.
- «Собери исследование, стратегию и презентацию» → планирование включается само, пользователь не видит внутреннюю кухню.
- «Сделай короче» после документа → правка того же артефакта, как продолжение диалога с ассистентом.
- «Сделай SWOT для Aurora» после документа → новая задача, а не «режим revision».

### Плохо

- Ощущение, что пользователь управляет пайплайном, а не разговаривает с сотрудником.
- Вопрос или консультация уходит в task/plan.
- Лишние подтверждения на простых задачах.
- Уточнения, после которых система без повторной оценки «пошла выполнять».
- «Готово» без результата.
- Mock research / stub memory, выдаваемые за реальный результат.
- Разные ответы на одно намерение из-за regex/keyword в Telegram или Learning.
- Executive, Runtime или Telegram «умнеют» и подменяют Product Decision.

---

## 9. Критерий приёмки изменений

Изменение считается корректным, только если одновременно:

1. Не нарушает Product Goal, архитектурные и Runtime Invariants.
2. Пользователь ближе к ощущению современного AI Assistant, а не workflow engine.
3. Product Decision остаётся у Executive; Capability Resolver / Planner / Runtime / Orchestrator только исполняют.
4. Простые диалоговые сценарии не запускают Planner и не выглядят как workflow.
5. После clarification намерение переоценивается, а не форсится в execution.
6. Выключенные capability отсутствуют и в prompt, и в registry.
7. Learning не влияет на DecisionType.

Если тесты зелёные, а инвариант нарушен — это баг продукта, не «технический компромисс».

---

## 10. Что сознательно не делать

- Не переписывать Runtime / LangGraph при выносе Conversation FSM.
- Не впихивать выбор capability pipeline внутрь Executive.
- Не считать «≥ N capabilities» критерием для Planner.
- Не подключать real web-search, пока не выбран стек.
- Не внедрять embeddings до выбора провайдера и оценки стоимости.
- Не добавлять keyword shortcuts «для надёжности».
- Не держать product-логику в Telegram «потому что так быстрее».
- Не показывать пользователю планы / quality / memory как отдельные продукты.
- Не запускать Planner «на всякий случай».
- Не давать Skills / Orchestrator / Runtime право принимать Product Decision.
- Не делать новый канал (Slack / Web), пока нет одного ConversationService.
- Не оптимизировать токены и «красивую архитектуру», пока есть silent-success и workflow-поведение в диалоге.
- Не формулировать задачу как «убрать process singleton» — формулировка: **перестать использовать process memory как источник истины** (кэш допустим).
- Не требовать «один класс Renderer» — требовать **единый Render Contract**.

---

## 11. План исправлений

Цель плана: привести код к Product Goal.  
Порядок: сначала убрать ложную готовность и side-channels, затем устойчивость пилота, затем production ops, затем assistant-grade UX.

### 11.1 Этап 0 — Зафиксировать контракт — DONE (this PR)

**Добавить / обновить**

- [x] Этот документ (`PRODUCT_GOAL.md`) — уже источник правды.
- [x] `docs/PRODUCTION_CONTRACT.md` — что гарантируем / не умеем (live news, research, semantic memory, PDF…) — **added this PR**.
- [x] `docs/DECISION_CONTRACT.md` — Executive = единственный owner Product Decision; запрет keyword / document routing; Runtime Invariants — **added this PR**.
- [x] `docs/CAPABILITY_MATRIX.md` — матрица capabilities: `prod` / `pilot` / `off` / `stub` (+ правило: off ⇒ нет в prompt и registry) — **added this PR**.

**Критерий:** любой PR можно отклонить ссылкой на раздел этого документа.

---

### 11.2 Этап 1 (P0) — Не врать пользователю и убрать обходные роутеры

#### P0-A. ChatGPT-like vs workflow (из реальных диалогов) — DONE (Sprint A)

Минимальные сценарии приёмки (покрыты policy + decision catalog + Telegram flow):

1. [x] «Какой курс доллара?» → `RESPOND`, без задачи и плана.
2. [x] «Сделай КП» → `EXECUTE` + линейный capability pipeline без Planner и без лишнего approve.
3. [x] «КП на AI автоматизацию» (уточнение / продолжение) → естественный диалог; повторная оценка Executive; не silent auto-execution.
4. [x] Вопрос / консультация / анализ → ответ.
5. [x] Создание артефакта → задача.
6. [x] Объективно сложная многоэтапная работа (зависимости / ветвление) → план, и только тогда.

#### P0-B. Stub skills и silent success — DONE (Sprint A; missing-status honesty this PR)

- [x] Убрать stubs из prod registry / prompt (`DocumentSkill` / `AnalysisSkill` / `FileSkill` не регистрируются).
- [x] Executor / Orchestrator: `status != completed` → FAIL, не COMPLETED; **dict без `status` → FAIL** (this PR).
- [x] Нет артефакта → пользователю не писать «Готово».
- [x] Неизвестная / disabled capability → fail на resolve (и отсутствует в prompt/registry).

#### P0-C. Один ConversationService (без rewrite Runtime) — DONE (Sprint B)

- [x] Перенести orchestration пользовательского диалога в application layer (`app.conversation`).
- [x] **Не** переписывать Runtime. **Не** переписывать LangGraph.
- [x] Telegram (и любой канал) = map / send only — ports (`SessionPort` / `ChannelNotifier` / …); `ConversationService` без `app.adapters.telegram` imports.
- [x] Любой новый канал использует тот же ConversationService без дублирования логики (wire ports).
- [x] Runtime остаётся исполнителем уже принятого Product Decision (см. Runtime Invariants).
- Note: `ConversationState.user_id` / `chat_id` keep Redis JSON aliases `telegram_user_id` / `telegram_chat_id`.

#### P0-D. Состояние диалога — DONE (Sprint B)

- [x] Async ConversationStore API + per-user lock (`user_lock`).
- [x] RedisConversationStore (`conversation:fsm:{user_id}`, TTL `conversation_fsm_ttl_seconds`).
- [x] Production bootstrap → Redis store; tests → InMemory singleton.
- [x] Session bindings (`conversation:binding:{user_id}`) — Redis; durable workspace lookup by client_id уже есть.
- [x] Restart и `workers > 1` не ломают clarify / approval / revision (при Redis FSM).

#### P0-E. Clarification — DONE (Sprint B)

- [x] Повторный `ASK_CLARIFICATION` → снова спросить, pending не сбрасывать в execute.
- [x] После ответа пользователя — **повторная оценка намерения Executive**.
- [x] Merge original goal + answers (Telegram clarification path).
- [x] Context Builder: merge transport; не меняет смысл запроса; **не удаляет transport context** вне политики truncation.

#### P0-F. Запрет Keyword / Document Routing — DONE (Sprint A)

- [x] Удалить revision regex-gate из decision path; после артефакта решение только через Executive + context.
- [x] Keyword learning / feedback routers не являются decision path.
- [x] Убрать document-type routing (`_wants_presentation` — только capability `presentation_design`).
- [x] Runtime / Telegram не превращают Revision ↔ New Task самостоятельно.

#### P0-G. Security + honesty + readiness — PARTIAL (Sprint A leftovers this PR)

- [x] Нельзя создавать ADMIN anonymously; Telegram allowlist: `None` = no filter (dev), empty set = deny all, non-empty = allowlist; **production + empty → deny all + error log** (this PR).
- [x] Persist API keys / audit (не process memory как источник истины) — Redis provider; InMemory в tests/dev.
- [x] Production: Redis security store / rate limiter **fail-closed** (no InMemory fallback) — this PR.
- [x] `/ready`: обязательные сервисы определяют readiness; optional → **DEGRADED**, не **NOT READY**.
- [x] Research: feature flag OFF (`research_enabled=False`); нет в prompt и registry.
- [x] Semantic memory: feature flag OFF (`semantic_memory_enabled=False`); нет в product surface.

---

### 11.3 Этап 2 (P1) — Пилот как AI Employee

#### P1-A. Approval только когда нужен сложный multi-stage plan

- [x] Простые `EXECUTE` (в т.ч. линейный multi-skill pipeline) — без лишних подтверждений.
- [x] Approve = resume from stored plan/decision (`skip_executive_llm` + `resume_task_plan`), **не** LangGraph checkpoint / MemorySaver.
- [x] Persist execution state Redis (`RedisCheckpointManager` app-level blobs, TTL) in production; tests/dev → MemorySaver / InMemory — **PARTIAL**: LangGraph interrupt checkpointer still MemorySaver (`langgraph.checkpoint.redis` not in deps).

#### P1-B. Context Builder

- [x] Merge transport context ∪ built context (Sprint B).
- [x] Никогда не изменять смысл пользовательского запроса — только агрегировать.
- [x] Не удалять transport context вне политики truncation.
- [ ] Relevant recall; пустой knowledge search → пусто (не dump) — partial / follow-up.
- [x] Truncate history по явной политике (`context_history_max_messages`, default 20).
- [x] Learning inject только preference-слой с confidence filter.

#### P1-C. Planner только по решению Executive и правильному критерию

- [x] Planner только после Product Decision `CREATE_PLAN`.
- [x] Критерий: зависимости / ветвление / `requires_llm_plan` — **не** «число capabilities ≥ N».
- [x] «Создай КП» с линейной цепочкой skills → без LLM Planner (`build_direct_execution_plan`).
- [x] Никаких самостоятельных запусков Planner из adapter / skills / Runtime.

#### P1-D. Capability Resolver + Skills + Render Contract + Orchestrator

- [x] После `EXECUTE`/`CREATE_PLAN` Capability Resolver **owns** final ordered capability graph (soft hints from Executive; drop unknown/disabled; `CAPABILITY_ORDER`; fail-closed if empty — no keyword invent from user text).
- [x] Skill не знает, какая Skill будет следующей.
- [x] Orchestrator знает только DAG; убраны capability-specific if (`presentation_design` / `document_rendering`).
- [x] Единый Render Contract — `DocumentRendererService.render(RenderRequest)` product entry (module docstring).
- [x] Dead dual document nodes удалить или не использовать — unregistered from `build_executive_graph` (skills path intact).
- [x] PDF: не предлагать в product surface (Executive prompt / DocumentRenderSkill reject); `PdfRenderer` stub raises — implement later.

#### P1-E. Learning строго по контракту

- [x] Только стиль / формат / язык / оформление / предпочтения (durable markers).
- [x] Не меняет стратегию выполнения.
- [x] **Никогда не влияет на DecisionType Executive.**
- [x] Убрать fragile markers (`короче` one-off revision → не durable learning).
- [x] Confidence filter на read path (`get_applicable_rules` / `apply_rules`).
- [x] Не auto-learn one-off правок документа как durable rules.

#### P1-F. Knowledge

- [x] Не auto-remember на низком пороге — `DEFAULT_MIN_CONFIDENCE=0.7`.
- [x] Persist только при `persist=True` / confirm metadata (default `persist=False`) + confidence gate.

#### P1-G. LLM degrade

- [x] Strategy / Presentation / Quality (document): controlled fail + degraded metadata.
- [x] OpenRouter: retry / backoff на 429 / 5xx (3 attempts).

#### P1-H. Decision eval

- [x] Policy catalog / scenario fixtures (existing).
- [ ] Golden + spot live Executive — open.
- [x] Catalog honesty: fixture routing ≠ live LLM proof (noted in DECISION_CONTRACT / scenario module docstring).
- [x] Runtime не мутирует DecisionType (инвариант сохранён).

#### P1-I. Telegram ops hygiene

- [x] Короткие DB-транзакции в polling — `db_release` после resolve/history, до LLM.
- [x] При RUNNING — сообщение «ещё работаю», не параллельный второй pipeline.

---

### 11.4 Этап 3 (P2) — Production hardening

- [x] Redis AUTH, Qdrant key, MinIO pinned tags / deps (edge TLS external; MinIO plain inside network).
- [x] Resource limits (modest mem/cpus on prod compose); [ ] TLS at edge — open; [ ] backups schedule — open; [ ] rollback deploy playbook — open.
- [x] Migrations не на каждый multi-worker startup race (advisory lock + one-shot recommendation).
- [x] Sentry + metrics; wire LLM latency / tokens.
- [x] Tenant ACL на CRUD; safe artifact object keys; compensation MinIO ↔ DB.
- [x] Отдельный Telegram worker; shared Redis rate limit (**fail-closed**, no InMemory fallback in prod — this PR); idempotent update handling.
- [ ] Реальный task queue / Celery — open (только если нужны длинные background jobs).
- [x] Readiness: required vs degraded — закрепить в health контракте и compose/Dockerfile healthchecks.

---

### 11.5 Этап 4 (P3) — Assistant-grade UX

- Меньше progress theater на простых задачах.
- Continuity правок как у ChatGPT / Claude (без отдельного «режима движка»).
- Команды `/new`, `/status`, `/cancel` — явный контроль, не замена естественного диалога.
- Честные ответы про ограничения.
- **Отдельно (не впихивать в P0/P1):** выбор стека research и провайдера embeddings + оценка стоимости — только после стабилизации диалогового поведения. После включения — capability появляется и в registry, и в prompt одновременно.

---

## 12. Спринты

| Sprint | Статус | Фокус относительно Goal | Состав |
|--------|--------|-------------------------|--------|
| **A** | **PARTIAL** (`1edbb65` + leftovers this PR) | Не врать + убрать router side-channels + ChatGPT vs workflow | P0-A/B/F mostly done; P0-G fail-closed this PR; Stage 0 contracts this PR |
| **B** | **PARTIAL** | Один мозг + один FSM (без rewrite Runtime/LangGraph) + Runtime Invariants | P0-C DONE; P0-D DONE (incl. bindings); P0-E DONE |
| **C** | **PARTIAL** | Пилот: Resolver / Orchestrator / Learning / Planner criterion / LLM degrade / RUNNING gate | P1-A…P1-I; open: LangGraph Redis interrupt checkpointer, live LLM eval; PDF stub kept off surface |
| **D** | **PARTIAL** | Production ops | Landed: secrets, workers, ACL, observability, readiness; open: TLS, backups schedule, rollback playbook, Celery |
| **E** | pending | Assistant-grade + осознанный research/embeddings | Этап 4 (P3) |

### Sprint A — Definition of Done — PARTIAL (closing leftovers this PR)

- [x] Вопрос / консультация / анализ не уходят в task/plan.
- [x] «Курс доллара» / «Сделай КП» / уточнение КП ведут себя как ассистент, не как движок.
- [x] «Сделай КП» не запускает Planner только из-за числа skills.
- [x] Нет silent «Готово» без результата; dict skill result без `status` → FAIL.
- [x] Keyword / document routing убраны из decision path.
- [x] Research и semantic memory: flag OFF → нет в prompt и registry; не mock/stub в product surface.
- [x] `/ready`: optional deps = DEGRADED, не NOT READY.
- [x] Security hard gate (allowlist deny-all when empty in prod; Redis store/rate-limit fail-closed) — this PR.
- [x] Stage 0 contracts (`PRODUCTION_CONTRACT` / `DECISION_CONTRACT` / `CAPABILITY_MATRIX`) — this PR.

### Sprint B — Definition of Done — PARTIAL

- [x] ConversationService (`app.conversation`); Telegram = ports adapter (map/send only). FSM field aliases `telegram_*` retained for Redis JSON.
- [x] Process memory не источник истины для FSM (Redis в bootstrap; InMemory для тестов).
- [x] Clarification с повторной оценкой Executive; transport context не теряется Builder-ом.
- [x] Session bindings Redis (`conversation:binding:{user_id}`).
- [x] Runtime / LangGraph не переписаны «заодно».
- [x] Runtime не мутирует DecisionType и не запускает Planner сам (инвариант Sprint A сохранён).

### Sprint C — Definition of Done — PARTIAL

- [x] Executive = только Product Decision; Capability Resolver **owns** ordered capability graph (hints soft; fail-closed if empty).
- [x] Context Builder только агрегирует и merge transport; не меняет смысл; не удаляет transport context вне truncation policy.
- [x] Planner по зависимостям/ветвлению/`requires_llm_plan`, не по count(capabilities).
- [x] Orchestrator знает только DAG / зависимости / статусы (нет capability-name ifs).
- [x] Skills независимы; skill не знает следующего.
- [x] Единый Render Contract — `DocumentRendererService.render(RenderRequest)`.
- [x] Learning не влияет на DecisionType и стратегию выполнения; confidence filter + no one-off revision learn.
- [x] Простые EXECUTE без лишнего approve; multi-stage approval = **stored plan re-run** (не LangGraph checkpoint).
- [x] Redis app-level execution checkpoint (`RedisCheckpointManager`) in production — **PARTIAL**: LangGraph `MemorySaver` still used as interrupt checkpointer.
- [x] Controlled degrade на LLM outage для strategy / presentation / quality.
- [x] RUNNING busy gate в ConversationService.
- [x] P1-F knowledge auto-remember gate; P1-I short DB txns; dead document nodes unregistered.
- [x] PDF not offered on product surface (stub honest); history truncate policy; catalog ≠ live eval (noted).
- [ ] Live / golden Executive eval — open.

### Sprint D — Definition of Done — PARTIAL

- [x] Persist API keys / audit (Redis starter: `security:apikey:*`, `security:audit`); InMemory **только** tests/dev; prod fail-closed.
- [x] Redis AUTH (`REDIS_PASSWORD` / `--requirepass`); Qdrant API key wired in compose + env examples.
- [x] MinIO pinned image tag; `MINIO_SECURE=false` inside docker network (edge TLS external).
- [x] Migrations race-safe: Postgres advisory lock in entrypoint; prod recommends one-shot + `RUN_MIGRATIONS_ON_STARTUP=false`.
- [x] Separate Telegram worker (`python -m app.adapters.telegram.worker`); `TELEGRAM_INLINE_POLLING` gate in API lifespan.
- [x] Idempotent Telegram updates (`telegram:update:{id}` SET NX); Redis shared rate limit **fail-closed** (no InMemory fallback in prod).
- [x] Tenant ACL via API key `metadata.client_id` / `tenant_client_id` on clients/projects/artifacts (fail closed 403).
- [x] Safe artifact object keys + MinIO compensation on DB create failure; best-effort delete logged.
- [x] LLMGateway → `record_llm_call` (tokens/latency); Sentry init when `SENTRY_DSN` set.
- [x] Readiness: compose + Dockerfile HEALTHCHECK → `/ready`; qdrant healthcheck; modest prod resource limits.
- [ ] TLS at edge — open.
- [ ] Backups schedule — open.
- [ ] Rollback deploy playbook — open.
- [ ] Real task queue / Celery — open.

### Sprint E — Definition of Done

- Ощущение современного ассистента на типовых диалогах агентства.
- Research / embeddings включаются только после выбора стека и оценки стоимости; при включении — одновременно registry + prompt.

---

## 13. Уровни готовности продукта

### Pilot-ready

Пользователь не чувствует workflow engine:

- простые вопросы → сразу текст;
- простые задачи → без лишних approve и без лишнего Planner;
- нет keyword / document routing;
- Product Decision только у Executive;
- Capability Resolver / Planner / Runtime / Orchestrator только исполняют;
- один FSM; единый Render Contract;
- нет silent «Готово»;
- Telegram / Context / Planner / Orchestrator / Runtime не принимают Product Decision;
- research / semantic честно off (нет в prompt/registry) или реально работают после отдельного решения по стеку;
- clarification с повторной оценкой намерения;
- Learning не влияет на DecisionType.

### Production v1

Pilot + resilience / security / ops (Sprint D).

### Assistant-grade

Поведение по ощущению близко к ChatGPT / Claude / Gemini на типовых сценариях агентства (не сравнение качества модели, а UX-поведение).

---

## 14. Связанные документы

- `docs/PROJECT_CONTEXT.md` — контекст и видение проекта
- `docs/ARCHITECTURE.md` — техническая архитектура
- `docs/ROADMAP.md` — этапы развития
- `docs/RELEASE_CANDIDATE_REPORT.md` — статус RC / staging gates
- `docs/PRODUCTION_CONTRACT.md` — production guarantees / non-goals (Stage 0)
- `docs/DECISION_CONTRACT.md` — Product Decision owner + Runtime Invariants (Stage 0)
- `docs/CAPABILITY_MATRIX.md` — capability status matrix (Stage 0)
