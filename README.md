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
**Backend:** Python 3.12, FastAPI, PostgreSQL, Redis, Qdrant, MinIO  
**AI:** OpenRouter (через LLM Gateway), Mem0, Whisper  
**Frontend:** React / Next.js

## Структура репозитория

```
ai-employee-os/
├── backend/            # FastAPI backend
├── docker-compose.yml  # Local development stack
├── frontend/           # Admin panel и UI (React / Next.js)
├── infrastructure/     # CI/CD, deployment (planned)
└── docs/               # Архитектура, контекст, roadmap, ADR
```

## Требования

- [Docker](https://docs.docker.com/get-docker/) 24+
- [Docker Compose](https://docs.docker.com/compose/) v2+
- Git

Для локальной разработки без Docker (опционально):

- Python 3.12+
- PostgreSQL 16, Redis 7, Qdrant, MinIO — или используйте `docker compose` только для инфраструктуры

## Быстрый старт

### 1. Клонировать и настроить окружение

```bash
git clone https://github.com/pobedildo25/ai-employee-os.git
cd ai-employee-os
cp .env.example .env
```

Отредактируйте `.env` при необходимости. Для локальной разработки значения по умолчанию подходят.

### 2. Запустить все сервисы

```bash
docker compose up --build
```

Фоновый режим:

```bash
docker compose up --build -d
```

### 3. Проверить health endpoint

```bash
curl http://localhost:8000/health
```

Ожидаемый ответ при здоровых сервисах:

```json
{
  "status": "ok",
  "service": "ai-employee-os",
  "environment": "development",
  "trace_id": "...",
  "services": {
    "postgres": { "status": "up", "detail": "ok" },
    "redis": { "status": "up", "detail": "ok" },
    "qdrant": { "status": "up", "detail": "ok" },
    "minio": { "status": "up", "detail": "ok" }
  }
}
```

### Docker Compose сервисы

| Сервис | Порт | Назначение |
|--------|------|------------|
| backend | 8000 | FastAPI API |
| postgres | 5433 | Project & Client Memory |
| redis | 6380 | Session Memory, task state |
| qdrant | 6335 | Vector database (Knowledge Memory) |
| minio | 9000 | Object storage (документы, артефакты) |
| minio console | 9001 | Web UI MinIO |

### Полезные команды

```bash
# Статус контейнеров
docker compose ps

# Логи backend
docker compose logs -f backend

# Остановить
docker compose down

# Остановить и удалить volumes (очистка данных)
docker compose down -v
```

## Документация

| Документ | Описание |
|----------|----------|
| [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md) | Цели, принципы, возможности системы |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Компоненты, память, document intelligence |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Этапы разработки |
| [docs/ADR/](docs/ADR/) | Architecture Decision Records |

## Принципы разработки

- **Никаких жёстких сценариев** — агент сам решает, что делать
- **Skills как расширяемые возможности** — каждая функция — отдельный skill
- **Память на всех уровнях** — сессия, проект, клиент, знания, обучение
- **Observability by default** — trace_id, логи, история шагов
- **Human-in-the-loop** — approval для сложных задач

## Статус

**Этап 1 — Local Infrastructure Foundation** — Docker-окружение, FastAPI skeleton, health checks.

## Лицензия

Proprietary — внутренний проект маркетингового агентства.
