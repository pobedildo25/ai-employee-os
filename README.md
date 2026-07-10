# AI Employee OS

Универсальный AI-сотрудник для маркетингового агентства. Работает через Telegram и выполняет задачи как полноценный сотрудник — не чат-бот с жёсткими сценариями, а агентная AI-система.

## Что это

AI Employee OS принимает задачи на естественном языке, самостоятельно определяет цель, выбирает инструменты и выполняет работу: создаёт документы и презентации, анализирует звонки, работает с файлами, помнит клиентов и проекты, применяет фирменный стиль.

## Архитектура (кратко)

```
User Request → Executive Agent → Capability Planning → Task Planning
            → Skill Selection → Execution → Review → Memory Update
```

**Runtime:** LangGraph  
**Backend:** Python 3.12, FastAPI, PostgreSQL, Redis, Qdrant  
**AI:** OpenRouter (через LLM Gateway), Mem0, Whisper  
**Frontend:** React / Next.js

## Структура репозитория

```
ai-employee-os/
├── backend/          # Python backend, агенты, skills, API
├── frontend/         # Admin panel и UI (React / Next.js)
├── infrastructure/   # Docker, CI/CD, deployment
└── docs/             # Архитектура, контекст, roadmap, ADR
```

## Документация

| Документ | Описание |
|----------|----------|
| [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md) | Цели, принципы, возможности системы |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Компоненты, память, document intelligence |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Этапы разработки |
| [docs/ADR/](docs/ADR/) | Architecture Decision Records |

## Быстрый старт (планируется)

```bash
cp .env.example .env
# Заполните переменные окружения

# Backend (будет добавлен на следующих этапах)
cd backend && pip install -r requirements.txt

# Frontend (будет добавлен на следующих этапах)
cd frontend && npm install
```

## Принципы разработки

- **Никаких жёстких сценариев** — агент сам решает, что делать
- **Skills как расширяемые возможности** — каждая функция — отдельный skill
- **Память на всех уровнях** — сессия, проект, клиент, знания, обучение
- **Observability by default** — trace_id, логи, история шагов
- **Human-in-the-loop** — approval для сложных задач

## Статус

**Этап 0 — Foundation** — структура репозитория и документация.

## Лицензия

Proprietary — внутренний проект маркетингового агентства.
