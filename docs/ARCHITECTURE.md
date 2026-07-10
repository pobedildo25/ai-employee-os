# Architecture — AI Employee OS

## Overview

AI Employee OS — агентная система на базе **LangGraph** как agent runtime для workflow, состояния и выполнения графа. Вся бизнес-логика располагается поверх LangGraph.

### Request Pipeline

Порядок обработки каждого запроса:

```
User Request
    ↓
Context Builder              ← сбор контекста ДО входа в граф
    ↓
LangGraph Runtime
    Executive Agent
        ↓
    Capability Planner
        ↓
    Planner (если сложная задача)
        ↓
    Human Approval Layer (если требуется)
        ↓
    Task Executor → Skill Registry
        ↓
    Quality Gate (Reviewer Agent)
        ↓
    Artifact Versioning
        ↓
    Memory Update
```

Все LLM-вызовы внутри графа проходят через **LLM Gateway** → OpenRouter.

```
┌─────────────────────────────────────────────────────────────┐
│                      Telegram Interface                      │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                     FastAPI Backend                          │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │ LLM Gateway │  │Context Builder│  │ Human Approval Layer│ │
│  └──────┬──────┘  └──────┬───────┘  └──────────┬──────────┘ │
│         │                │                      │            │
│  ┌──────▼────────────────▼──────────────────────▼──────────┐ │
│  │                   LangGraph Runtime                      │ │
│  │  Executive → Capability → Planner → Executor → Reviewer │ │
│  └──────┬──────────────────────────────────────────┬───────┘ │
│         │                                          │         │
│  ┌──────▼──────┐                          ┌────────▼────────┐ │
│  │Skill Registry│                          │ Artifact System │ │
│  └─────────────┘                          └─────────────────┘ │
└─────────────────────────┬───────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
   ┌────▼────┐      ┌─────▼─────┐     ┌────▼────┐
   │PostgreSQL│      │   Redis   │     │ Qdrant  │
   │+ Vector  │      │  (Session)│     │(Knowledge)│
   └─────────┘      └───────────┘     └─────────┘
                          │
                     ┌────▼────┐
                     │  Mem0   │
                     │(Long Term)│
                     └─────────┘
```

## LangGraph Runtime

LangGraph — **agent runtime** системы. Не содержит бизнес-логику, а обеспечивает инфраструктуру выполнения агентов.

**Отвечает за:**
- **State** — единая схема состояния (`AgentState`) для всех узлов графа
- **Workflow** — определение и маршрутизация между узлами (Executive → Capability → Planner → Executor → Reviewer)
- **Graph execution** — последовательное и параллельное выполнение шагов
- **Checkpointing** — сохранение и восстановление состояния (для retry, approval pause, long-running tasks)
- **Conditional routing** — ветвление: простая задача vs сложная, нужен ли approval

**Не отвечает за:**
- Выбор конкретных skills (бизнес-логика Capability Planner)
- Генерацию документов (skills)
- Прямые вызовы LLM (только через LLM Gateway)

Каждый узел графа — чистая функция `(state) → state`. Observability: каждый переход логируется с `trace_id`.

## Core Components

### 1. Executive Agent

Главный интеллект системы. Точка входа для каждого запроса.

**Отвечает за:**
- Понимание запроса пользователя
- Определение цели и намерения
- Оценку сложности задачи
- Решение: нужен ли многошаговый план
- Маршрутизацию к Capability Planner или напрямую к Skill

**Не содержит:**
- Генерацию документов
- Работу с файлами
- Бизнес-логику конкретных доменов

### 2. Capability Planner

Определяет **какие способности** нужны для выполнения задачи.

**Пример:**

Запрос: *«Создай презентацию из звонка клиента»*

```
Capabilities:
  - Audio Processing
  - Whisper Transcription
  - Call Analysis
  - Presentation Generator
  - Brand Style Engine
```

### 3. Planner

Создаёт **план выполнения** для сложных задач.

- Декомпозиция на шаги
- Зависимости между шагами
- Оценка ресурсов и времени
- Передача плана в Human Approval Layer (при необходимости)

### 4. Task Executor

Выполняет задачи и шаги плана.

**Поддерживает:**
- Очередь задач
- Статусы (pending, running, completed, failed)
- Retry с backoff
- Обработку ошибок
- Отслеживание прогресса

### 5. Skill Registry

Все возможности системы — **отдельные Skills**, регистрируемые в едином реестре.

| Skill | Назначение |
|-------|-----------|
| Document Generator | Создание документов с нуля |
| Presentation Generator | Создание презентаций |
| Spreadsheet Analyzer | Анализ таблиц |
| Whisper Analyzer | Транскрипция и анализ аудио |
| Vision Analyzer | Анализ изображений |
| Browser Research | Веб-исследования |
| Analytics | Аналитика данных |
| Python Analysis | Вычисления и data science |
| Document Reverse Engineering | Извлечение структуры из документов |
| Brand Style Engine | Применение фирменного стиля |

Каждый Skill:
- Имеет чёткий контракт (input/output)
- Не знает о других Skills напрямую
- Вызывается через Task Executor
- Логирует все действия

### 6. Reviewer Agent (Quality Gate)

**Quality Gate** — обязательная проверка качества перед доставкой результата пользователю. Реализуется через Reviewer Agent.

Проверяет:
- Соответствие исходному запросу и цели
- Качество и полноту контента
- Применение Brand Profile / фирменного стиля
- Корректность структуры документа (сверка с Document AST)
- Наличие критичных ошибок

**Решения Quality Gate:**
- `pass` — результат доставляется пользователю
- `revise` — Task Executor повторяет шаг с замечаниями (retry)
- `escalate` — запрос уточнения у пользователя

Все решения Quality Gate логируются в observability trace.

## Cross-Cutting Concerns

### LLM Gateway

Все вызовы LLM проходят через единый слой. Агенты **не вызывают OpenRouter напрямую**.

```
Agent → LLM Gateway → OpenRouter API
              ↓
         - rate limiting
         - model routing
         - token accounting
         - retry / fallback
         - observability
```

### Context Builder

Выполняется **до Executive Agent** — первый шаг pipeline после получения запроса.

Собирает `ExecutionContext`:

| Источник | Данные |
|----------|--------|
| Запрос | Текст, вложения, метаданные Telegram |
| Session Memory (Redis) | Текущий диалог |
| Project Memory (PostgreSQL) | История проекта, задачи |
| Client Memory (PostgreSQL + vector) | Профиль, предпочтения, контекст клиента |
| Knowledge Memory (Qdrant) | Релевантные документы и фрагменты |
| Long Term Memory (Mem0) | Долгосрочные факты |
| Learning Memory | Правила из обратной связи |
| Brand Profile | Фирменный стиль клиента |
| Semantic Rules | Правила и ограничения клиента |

Результат передаётся в LangGraph как начальное состояние. Executive Agent работает уже с полным контекстом, а не с голым запросом.

### Human Approval Layer

Для сложных задач:

```
Plan → [User Approval] → Execution
```

- Пользователь видит план до выполнения
- Может одобрить, отклонить или скорректировать
- Таймаут ожидания approval

### Artifact Versioning

Все созданные и изменённые документы и файлы проходят через **Artifact System** с полным версионированием.

**Модель версии:**
```
Artifact
  ├── artifact_id        — стабильный идентификатор
  ├── version            — монотонно растущий номер (1, 2, 3…)
  ├── parent_version     — ссылка на предыдущую версию
  ├── task_id            — задача, породившая версию
  ├── client_id          — привязка к клиенту
  ├── skill              — skill, создавший артефакт
  ├── content_hash       — хеш содержимого для дедупликации
  ├── document_ast_ref   — ссылка на Document AST (если документ)
  └── created_at         — timestamp
```

**Правила:**
- Каждая генерация или правка создаёт новую версию (immutability)
- Пользователь может запросить любую предыдущую версию
- Quality Gate может инициировать `revise` → новая версия
- Admin Panel показывает полную историю версий

### Observability

Каждый запрос получает сквозной `trace_id` при входе в систему. Все компоненты наследуют его.

**Что логируется:**

| Уровень | Данные |
|---------|--------|
| Request | trace_id, user_id, client_id, raw request |
| Context Builder | источники контекста, объём данных |
| LangGraph | переходы между узлами, state diffs |
| LLM Gateway | model, tokens, latency, cost |
| Skills | input/output, duration, errors |
| Quality Gate | решение (pass/revise/escalate), замечания |
| Artifacts | artifact_id, version, skill |

**История выполнения** доступна:
- В Admin Panel (trace viewer)
- По `trace_id` для отладки
- Для обучения (Learning Memory) при получении feedback

## Memory Architecture

| Уровень | Хранилище | Назначение |
|---------|-----------|-----------|
| Session Memory | Redis | Текущий диалог, временный контекст |
| Project Memory | PostgreSQL | История проекта, задачи, артефакты |
| Client Memory | PostgreSQL + Vector Search | Профиль клиента, предпочтения, контекст |
| Knowledge Memory | Qdrant | Семантический поиск по документам и знаниям |
| Long Term Memory | Mem0 | Долгосрочные факты и отношения |
| Learning Memory | PostgreSQL | Правила и предпочтения из обратной связи |

### Client Knowledge Pipeline & Knowledge Migration

**Knowledge Migration** — процесс переноса существующей истории агентства в систему. Критичен для onboarding: AI должен знать клиента до первой задачи.

**Источники миграции:**
- Коммерческие предложения (КП)
- Презентации
- Отчёты
- Документы и договоры
- Записи звонков
- Брендбуки

**Pipeline:**

```
Upload
    ↓
Ingestion & Parsing (формат-агностичный)
    ↓
Document Reverse Engineering → Document AST
    ↓
Brand Style Engine → Brand Profile
    ↓
Embedding & Indexing → Qdrant (Knowledge Memory)
    ↓
┌──────────────┬──────────────┬──────────────┬──────────────┐
│Client Profile│Client Memory │Knowledge Base│Semantic Rules│
└──────────────┴──────────────┴──────────────┴──────────────┘
```

**Client Memory** — оперативный контекст клиента для Context Builder:
- Структурированный профиль (PostgreSQL)
- Семантический поиск по истории (vector search)
- Предпочтения, ограничения, tone of voice
- Ссылки на ключевые артефакты

**Knowledge Base** — долгосрочное хранилище знаний (Qdrant):
- Чанки документов с embeddings
- Метаданные: тип, дата, проект, клиент
- Используется Context Builder'ом для retrieval

## Document Intelligence

Документы — ключевая часть продукта.

### Возможности

1. Создать документ с нуля
2. Проанализировать существующий документ
3. Понять структуру документа (reverse engineering)
4. Создать шаблон из существующего документа
5. Сгенерировать документ для нового клиента по аналогии
6. Применить фирменный стиль

### Внутренние абстракции

#### Document AST

**Document AST** (Abstract Syntax Tree) — каноническое представление структуры документа, независимое от формата файла (.docx, .pptx, .pdf).

```
DocumentNode (root)
  ├── metadata: { title, author, client_id, brand_profile_ref }
  ├── sections: SectionNode[]
  │     ├── heading: { level, text, style }
  │     ├── content: ContentNode[]
  │     │     ├── ParagraphNode { text, style, tone }
  │     │     ├── TableNode { headers, rows, style }
  │     │     ├── ImageNode { ref, alt, position }
  │     │     └── ListNode { items, ordered }
  │     └── layout: { columns, spacing, alignment }
  └── styles: StyleMap { fonts, colors, margins }
```

**Используется:**
- Document Reverse Engineering — AST из существующего документа
- Template Engine — генерация нового документа из AST
- Brand Style Engine — применение стилей к узлам AST
- Quality Gate — валидация структуры результата

#### Artifact System

Хранение, версионирование, метаданные файлов (см. Artifact Versioning).

#### Template Engine

Генерация документов из Document AST + Brand Profile. Поддерживает: создание с нуля, клонирование по аналогии, применение шаблона к новому клиенту.

### Document Reverse Engineering

Отдельный Skill и ключевой этап Knowledge Migration.

**Задача:** из существующего документа извлечь структуру, стиль и логику — без копирования контента.

**Этапы:**
1. **Parse** — загрузка файла, определение формата
2. **Extract structure** — заголовки, секции, таблицы, списки → Document AST
3. **Extract style** — шрифты, цвета, отступы → StyleMap
4. **Extract patterns** — повторяющиеся блоки, логика секций
5. **Create template** — обобщённый AST-шаблон для новых документов

**Результат:**
- Document AST (конкретный документ)
- Template AST (обобщённый шаблон)
- Brand Profile update (если обнаружен стиль)

**Пример:** агентство загружает 10 КП одного клиента → Reverse Engineering выявляет типовую структуру (обложка → о компании → услуги → кейсы → контакты) → Template Engine использует её для нового клиента.

## Brand Style Engine

Отдельный компонент и Skill. Извлекает фирменный стиль из материалов и применяет при генерации.

**Два режима:**

| Режим | Когда | Результат |
|-------|-------|-----------|
| **Extract** | Knowledge Migration, загрузка брендбука | Brand Profile |
| **Apply** | Генерация документа/презентации | Стилизованный артефакт |

**Источники (Extract):**
- Брендбуки (PDF, изображения)
- Исторические документы агентства
- Презентации
- Результаты Document Reverse Engineering

**Извлекается в Brand Profile:**
- Цветовая палитра (primary, secondary, accent)
- Шрифты и типографика (заголовки, body, captions)
- Структура документов (типовые секции, порядок)
- Tone of voice (формальный, дружелюбный, экспертный)
- Правила оформления (логотип, отступы, фоны слайдов)

**Apply:** Brand Profile накладывается на Document AST перед рендерингом через Template Engine. Quality Gate проверяет соответствие Brand Profile.

## Tech Stack

| Слой | Технологии |
|------|-----------|
| Runtime | LangGraph |
| Backend | Python 3.12, FastAPI, SQLAlchemy |
| Databases | PostgreSQL, Redis, Qdrant |
| AI | OpenRouter (LLM Gateway), Mem0, Whisper |
| Documents | python-docx, python-pptx, openpyxl, reportlab |
| Frontend | React / Next.js |
| Infrastructure | Docker |

## Admin Panel

Отдельная панель управления (frontend):

- Память (просмотр, редактирование, очистка)
- База знаний (документы, индексация)
- Клиенты (профили, onboarding)
- Задачи (очередь, статусы, история)
- Логи и observability (trace viewer)

## Связанные документы

- [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)
- [ROADMAP.md](ROADMAP.md)
- [ADR/](ADR/)
