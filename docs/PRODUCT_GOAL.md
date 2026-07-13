# Product Goal — NOVA

**Статус:** источник правды для продукта, архитектуры и плана исправлений.  
Любой PR, который нарушает этот документ, отклоняется — даже при зелёных тестах.

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

### 11.1 Этап 0 — Зафиксировать контракт

**Добавить / обновить**

- Этот документ (`PRODUCT_GOAL.md`) — уже источник правды.
- `docs/PRODUCTION_CONTRACT.md` — что гарантируем / не умеем (live news, research, semantic memory, PDF…).
- `docs/DECISION_CONTRACT.md` — Executive = единственный owner Product Decision; запрет keyword / document routing; Runtime Invariants.
- Матрица capabilities: `enabled` / `stub` / `prod` / `pilot` / `off` (+ правило: off ⇒ нет в prompt и registry).

**Критерий:** любой PR можно отклонить ссылкой на раздел этого документа.

---

### 11.2 Этап 1 (P0) — Не врать пользователю и убрать обходные роутеры

#### P0-A. ChatGPT-like vs workflow (из реальных диалогов)

**Исправить** различие между ChatGPT-подобным поведением и workflow-поведением.

Минимальные сценарии приёмки:

1. «Какой курс доллара?» → `RESPOND`, без задачи и плана.
2. «Сделай КП» → `EXECUTE` + линейный capability pipeline без Planner и без лишнего approve.
3. «КП на AI автоматизацию» (уточнение / продолжение) → естественный диалог; повторная оценка Executive; не silent auto-execution.
4. Вопрос / консультация / анализ → ответ.
5. Создание артефакта → задача.
6. Объективно сложная многоэтапная работа (зависимости / ветвление) → план, и только тогда.

#### P0-B. Stub skills и silent success

- Убрать stubs из prod registry / prompt.
- Executor / Orchestrator: `status != completed` → FAIL, не COMPLETED.
- Нет артефакта → пользователю не писать «Готово».
- Неизвестная / disabled capability → fail на resolve (и отсутствует в prompt/registry).

#### P0-C. Один ConversationService (без rewrite Runtime)

- Перенести orchestration пользовательского диалога в application layer.
- **Не** переписывать Runtime. **Не** переписывать LangGraph.
- Telegram (и любой канал) = map / send only.
- Любой новый канал использует тот же ConversationService без дублирования логики.
- Runtime остаётся исполнителем уже принятого Product Decision (см. Runtime Invariants).

#### P0-D. Состояние диалога

- Перестать использовать process memory как источник истины.
- Durable store (Redis / Postgres) + per-user lock.
- Локальный кэш допустим только как cache, не как единственное хранилище.
- Restart и `workers > 1` не ломают clarify / approval / revision.

#### P0-E. Clarification

- Повторный `ASK_CLARIFICATION` → снова спросить, pending не сбрасывать в execute.
- После ответа пользователя — **повторная оценка намерения Executive**.
- Merge без meta-текста как единственного `user_input`; хранить original goal + answers отдельно в context.
- Context Builder: merge transport; не меняет смысл запроса; **не удаляет transport context** вне политики truncation.

#### P0-F. Запрет Keyword / Document Routing

- Удалить revision regex-gate; после артефакта решение только через Executive + context.
- Убрать keyword learning / feedback routers как decision path.
- Убрать document-type routing (`_wants_presentation` и аналоги).
- Runtime / Telegram не превращают Revision ↔ New Task самостоятельно.

#### P0-G. Security + honesty + readiness

- Нельзя создавать ADMIN anonymously; Telegram allowlist в prod; закрыть `/docs` в prod.
- Persist API keys / audit (не process memory как источник истины).
- `/ready`: обязательные сервисы определяют readiness; optional → **DEGRADED**, не **NOT READY**.
- Research: feature flag OFF, пока нет выбранного стека; нет в prompt и registry; mock-ready запрещён.
- Semantic memory: feature flag OFF, пока нет провайдера embeddings и оценки стоимости; нет в product surface; stub-embed запрещён.

---

### 11.3 Этап 2 (P1) — Пилот как AI Employee

#### P1-A. Approval только когда нужен сложный multi-stage plan

- Простые `EXECUTE` (в т.ч. линейный multi-skill pipeline) — без лишних подтверждений.
- Approve = resume checkpoint, не full re-run с нуля.
- Persist execution / checkpoint (не process memory как source of truth).

#### P1-B. Context Builder

- Merge transport context ∪ built context.
- Никогда не изменять смысл пользовательского запроса — только агрегировать.
- Не удалять transport context вне политики truncation.
- Relevant recall; пустой knowledge search → пусто (не dump).
- Truncate history по явной политике.
- Learning inject только preference-слой с confidence filter.

#### P1-C. Planner только по решению Executive и правильному критерию

- Planner только после Product Decision `CREATE_PLAN`.
- Критерий: зависимости / ветвление / объективно сложная многоэтапная работа — **не** «число capabilities ≥ N».
- «Создай КП» с линейной цепочкой skills → без Planner.
- Никаких самостоятельных запусков Planner из adapter / skills / Runtime.

#### P1-D. Capability Resolver + Skills + Render Contract + Orchestrator

- После `EXECUTE` capability graph строит Capability Resolver, не Executive.
- Skill не знает, какая Skill будет следующей.
- Orchestrator знает только DAG и зависимости/статусы; не знает бизнес-смысл capability.
- Убрать capability-specific if из Orchestrator.
- Единый Render Contract (один вход); реализации форматов могут быть разными классами.
- Dead dual document nodes удалить или не использовать.
- PDF: реализовать позже или не предлагать в surface.

#### P1-E. Learning строго по контракту

- Только стиль / формат / язык / оформление / предпочтения.
- Не меняет стратегию выполнения.
- **Никогда не влияет на DecisionType Executive.**
- Убрать fragile markers (`once`, one-off revision words как durable learning).
- Confidence filter на read path.
- Не auto-learn one-off правок документа как durable rules.

#### P1-F. Knowledge

- Не auto-remember на низком пороге.
- Persist только при достаточном confidence и / или явном confirm / review queue.

#### P1-G. LLM degrade

- Strategy / Presentation / Quality (document): controlled fail + понятный retry пользователю.
- OpenRouter: retry / backoff на 429 / 5xx.

#### P1-H. Decision eval

- Golden + spot live: Executive реально выбирает Product Decision как ассистент.
- Policy catalog ≠ доказательство live поведения — документировать честно.
- Проверять, что Runtime не мутирует DecisionType.

#### P1-I. Telegram ops hygiene

- Короткие DB-транзакции в polling (не держать session на весь LLM).
- При RUNNING — сообщение «ещё работаю», не параллельный второй pipeline без политики.

---

### 11.4 Этап 3 (P2) — Production hardening

- Redis AUTH, Qdrant key, MinIO secure + pinned tags / deps.
- Resource limits, TLS, backups, rollback deploy.
- Migrations не на каждый multi-worker startup race.
- Sentry + metrics; wire LLM latency / tokens.
- Tenant ACL на CRUD; safe artifact object keys; compensation MinIO ↔ DB.
- Отдельный Telegram worker; shared rate limit; idempotent update handling.
- Реальный task queue только если нужны длинные background jobs.
- Readiness: required vs degraded — закрепить в health контракте и compose healthchecks.

---

### 11.5 Этап 4 (P3) — Assistant-grade UX

- Меньше progress theater на простых задачах.
- Continuity правок как у ChatGPT / Claude (без отдельного «режима движка»).
- Команды `/new`, `/status`, `/cancel` — явный контроль, не замена естественного диалога.
- Честные ответы про ограничения.
- **Отдельно (не впихивать в P0/P1):** выбор стека research и провайдера embeddings + оценка стоимости — только после стабилизации диалогового поведения. После включения — capability появляется и в registry, и в prompt одновременно.

---

## 12. Спринты

| Sprint | Фокус относительно Goal | Состав |
|--------|-------------------------|--------|
| **A** | Не врать + убрать router side-channels + ChatGPT vs workflow | P0-A, P0-B, P0-E (clarify fix), P0-F, P0-G |
| **B** | Один мозг + один FSM (без rewrite Runtime/LangGraph) + Runtime Invariants | P0-C, P0-D, добить P0-E |
| **C** | Пилот: Context / Resolver / Skills / Orchestrator / Render Contract / Learning / Planner criterion | P1-A … P1-I |
| **D** | Production ops | Этап 3 (P2) |
| **E** | Assistant-grade + осознанный research/embeddings | Этап 4 (P3) |

### Sprint A — Definition of Done

- Вопрос / консультация / анализ не уходят в task/plan.
- «Курс доллара» / «Сделай КП» / уточнение КП ведут себя как ассистент, не как движок.
- «Сделай КП» не запускает Planner только из-за числа skills.
- Нет silent «Готово» без результата.
- Keyword / document routing убраны из decision path.
- Research и semantic memory: flag OFF → нет в prompt и registry; не mock/stub в product surface.
- `/ready`: optional deps = DEGRADED, не NOT READY.
- Security hard gate (allowlist, keys, docs) закрыт для prod-конфига.

### Sprint B — Definition of Done

- Один ConversationService; Telegram только transport.
- Process memory не источник истины для FSM.
- Clarification всегда с повторной оценкой Executive; transport context не теряется Builder-ом.
- Runtime / LangGraph не переписаны «заодно».
- Runtime не мутирует DecisionType и не запускает Planner сам.

### Sprint C — Definition of Done

- Executive = только Product Decision; capability graph строит Capability Resolver.
- Context Builder только агрегирует и merge transport; не меняет смысл; не удаляет transport context вне truncation policy.
- Planner по зависимостям/ветвлению/сложности, не по count(capabilities).
- Orchestrator знает только DAG / зависимости / статусы.
- Skills независимы; skill не знает следующего.
- Единый Render Contract (не обязательно один класс).
- Learning не влияет на DecisionType и стратегию выполнения.
- Простые EXECUTE без лишнего approve; сложный multi-stage approval = resume.
- Controlled degrade на LLM outage для strategy / presentation / quality.

### Sprint D — Definition of Done

- Tenant ACL, observability, idempotency, infra secrets, workers-safe FSM, backups/rollback, readiness contract закреплён в ops.

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
