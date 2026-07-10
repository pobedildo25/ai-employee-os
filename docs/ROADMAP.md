# Roadmap — AI Employee OS

## Этап 0 — Foundation ✅

**Цель:** Фундамент репозитория и документация.

- [x] Структура репозитория
- [x] PROJECT_CONTEXT.md
- [x] ARCHITECTURE.md
- [x] ROADMAP.md
- [x] ADR framework
- [x] README.md, .env.example, .gitignore
- [x] Архитектурный аудит: LangGraph, LLM Gateway, Context Builder, Quality Gate, Knowledge Migration, Document AST

---

## Этап 1 — Infrastructure & Backend Skeleton

**Цель:** Запускаемый backend с инфраструктурой.

- [ ] Docker Compose (PostgreSQL, Redis, Qdrant)
- [ ] FastAPI application skeleton
- [ ] SQLAlchemy models (базовые: User, Client, Project, Task)
- [ ] Конфигурация через pydantic-settings
- [ ] Health check endpoints
- [ ] Базовое логирование с trace_id
- [ ] LLM Gateway (базовая реализация → OpenRouter)

**Результат:** `docker compose up` поднимает все сервисы, API отвечает на `/health`.

---

## Этап 2 — LangGraph Core & Executive Agent

**Цель:** Агентный runtime и точка входа.

- [ ] LangGraph graph definition
- [ ] State schema (AgentState)
- [ ] Executive Agent node
- [ ] Capability Planner node
- [ ] Базовый routing (простая vs сложная задача)
- [ ] Context Builder (до Executive Agent)
- [ ] Observability: trace, step history

**Результат:** Запрос обрабатывается графом, Executive Agent определяет цель и маршрут.

---

## Этап 3 — Memory Layer

**Цель:** Все уровни памяти работают.

- [ ] Session Memory (Redis)
- [ ] Project Memory (PostgreSQL)
- [ ] Client Memory (PostgreSQL + embeddings)
- [ ] Knowledge Memory (Qdrant ingestion + search)
- [ ] Mem0 integration (Long Term Memory)
- [ ] Learning Memory (feedback rules)

**Результат:** Система помнит контекст между сессиями и клиентами.

---

## Этап 4 — Skill Registry & Task Executor

**Цель:** Расширяемая система skills и выполнение задач.

- [ ] Skill Registry (регистрация, discovery, контракты)
- [ ] Task Executor (очередь, статусы, retry)
- [ ] Planner node (декомпозиция сложных задач)
- [ ] Human Approval Layer
- [ ] Reviewer Agent (Quality Gate)
- [ ] Первые skills:
  - [ ] Document Generator (базовый)
  - [ ] Python Analysis

**Результат:** Задачи выполняются через skill pipeline с retry и review.

---

## Этап 5 — Document Intelligence

**Цель:** Полноценная работа с документами.

- [ ] Document AST parser
- [ ] Artifact System (storage, versioning)
- [ ] Template Engine
- [ ] Document Reverse Engineering skill
- [ ] Presentation Generator skill
- [ ] Spreadsheet Analyzer skill
- [ ] Brand Style Engine (извлечение + применение)

**Результат:** AI создаёт, анализирует и клонирует документы с бренд-стилем.

---

## Этап 6 — Audio & Vision

**Цель:** Мультимодальные возможности.

- [ ] Whisper Analyzer skill (транскрипция + анализ звонков)
- [ ] Vision Analyzer skill
- [ ] Browser Research skill
- [ ] Analytics skill

**Результат:** Система работает с аудио, изображениями и веб-данными.

---

## Этап 7 — Telegram Interface

**Цель:** Основной канал взаимодействия.

- [ ] Telegram bot (aiogram / python-telegram-bot)
- [ ] Webhook mode
- [ ] Приём текста, файлов, голосовых
- [ ] Отправка результатов и артефактов
- [ ] Inline approval для планов
- [ ] Progress updates

**Результат:** Сотрудник агентства работает с AI через Telegram.

---

## Этап 8 — Client Knowledge & Knowledge Migration

**Цель:** Загрузка и миграция истории агентства в систему.

- [ ] Knowledge Migration pipeline (upload → ingest → index)
- [ ] Upload pipeline (КП, презентации, отчёты, звонки, брендбуки)
- [ ] Document Reverse Engineering при миграции
- [ ] Brand Style Engine (Extract) → Brand Profile
- [ ] Client Profile generation
- [ ] Client Memory (PostgreSQL + vector search)
- [ ] Knowledge Base indexing (Qdrant)
- [ ] Semantic Rules extraction

**Результат:** Новый клиент onboarding'ится загрузкой материалов; Context Builder получает полный Client Memory.

---

## Этап 9 — Admin Panel (Frontend)

**Цель:** Панель управления системой.

- [ ] Next.js application
- [ ] Клиенты и проекты
- [ ] Память и знания
- [ ] Задачи и очередь
- [ ] Trace viewer / логи
- [ ] Artifact browser

**Результат:** Администратор управляет системой через web UI.

---

## Этап 10 — Learning & Production Hardening

**Цель:** Обучение на feedback и production-ready.

- [ ] Learning Memory (обратная связь → правила)
- [ ] Feedback loop в Reviewer Agent
- [ ] Rate limiting, security hardening
- [ ] CI/CD pipeline
- [ ] Monitoring & alerting (Sentry, metrics)
- [ ] Load testing
- [ ] Documentation для deployment

**Результат:** Production-ready система с непрерывным улучшением.

---

## Принципы приоритизации

1. **Агентное ядро раньше интерфейса** — сначала LangGraph, потом Telegram
2. **Память раньше skills** — контекст важнее инструментов
3. **Один skill за раз** — каждый skill полностью рабочий перед следующим
4. **Observability с первого дня** — trace_id и логи с этапа 1
5. **Никаких жёстких сценариев** — каждый этап проверяется на соответствие принципу

## Метрики успеха по этапам

| Этап | Критерий готовности |
|------|-------------------|
| 1 | `docker compose up` + `/health` OK |
| 2 | Запрос проходит через LangGraph graph |
| 3 | Контекст клиента доступен в новой сессии |
| 4 | Skill выполняется с retry и review |
| 5 | Документ создан с бренд-стилем |
| 6 | Звонок транскрибирован и проанализирован |
| 7 | Задача принята и выполнена через Telegram |
| 8 | Клиент onboarded загрузкой материалов |
| 9 | Admin panel показывает задачи и логи |
| 10 | Feedback улучшает поведение системы |
