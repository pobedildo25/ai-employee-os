# AI Employee OS

Универсальный AI-сотрудник для маркетингового агентства. Работает через Telegram и REST API как агентная система — не чат-бот с жёсткими сценариями.

## Что это

AI Employee OS принимает задачи на естественном языке, планирует работу, выбирает skills и выполняет задачи: документы, артефакты, знания клиента, workspace, фоновые задачи.

## Архитектура (кратко)

```
User Request → Context Builder → Executive Agent → Skills / Planning
            → Execution → Quality / Revision → Memory / Knowledge
```

**Runtime:** LangGraph  
**Backend:** Python 3.12, FastAPI, PostgreSQL, Redis, Qdrant, MinIO  
**AI:** OpenRouter через LLM Gateway  
**Transports:** Web API (`/api/v1`), Telegram Adapter  
**Cross-cutting:** Observability, Security (API keys, audit, rate limit)

## Структура репозитория

```
ai-employee-os/
├── backend/                 # FastAPI backend
│   ├── app/                 # application code
│   ├── alembic/             # DB migrations
│   ├── scripts/             # backup/restore
│   ├── docker/entrypoint.sh # prod startup + migrations
│   └── Dockerfile
├── docker-compose.yml       # local development
├── docker-compose.prod.yml  # production stack
├── .env.example             # local env template
├── .env.production.example  # production env template
├── .github/workflows/ci.yml # CI (test + docker build)
└── docs/                    # architecture, roadmap, ADR
```

## Требования

- Docker 24+ / Docker Compose v2+
- Git
- (optional) Python 3.12+ for local pytest

## Local setup

```bash
git clone https://github.com/pobedildo25/ai-employee-os.git
cd ai-employee-os
cp .env.example .env
docker compose up -d --build
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

- `/health` — liveness (процесс жив)
- `/ready` — readiness (postgres, redis, qdrant, minio)

API docs: http://localhost:8000/docs

### Development services

| Service | Host port | Role |
|---------|-----------|------|
| backend | 8000 | FastAPI |
| postgres | 5433 | primary DB |
| redis | 6380 | short-term memory |
| qdrant | 6335 | vectors |
| minio | 9000 / 9001 | artifacts |

```bash
docker compose logs -f backend
docker compose down
```

### Local tests

```bash
cd backend
python -m pip install -r requirements.txt
python -m pytest -q
```

### Migrations (local)

```bash
cd backend
alembic upgrade head
alembic current
```

Dev compose does **not** auto-migrate; run Alembic when schema changes.

## Production setup

1. Copy env template and fill secrets (do not commit `.env.production`):

```bash
cp .env.production.example .env.production
```

2. Start production stack:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

3. Verify:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Production notes:

- `APP_ENV=production`, `APP_DEBUG=false`
- `RUN_MIGRATIONS_ON_STARTUP=true` runs `alembic upgrade head` before uvicorn
- backend healthcheck uses `/ready`
- Dockerfile runs as non-root user `app` (uid 10001)
- isolated network `ai-employee-prod`, persistent volumes, `restart: always`
- DB connection pooling via `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_POOL_TIMEOUT` / `DB_POOL_RECYCLE`

## Environment variables

See `.env.example` (dev) and `.env.production.example` (prod).

Key groups:

- Application: `APP_ENV`, `APP_SECRET_KEY`, `LOG_LEVEL`
- Database: `DATABASE_URL`, `DB_POOL_*`
- Redis / Qdrant / MinIO
- LLM: `OPENROUTER_API_KEY`, model names
- Telegram: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ENABLED`
- Security: `SECURITY_ENABLED`, rate limit settings

Never commit real secrets.

## Backup / restore

Documented in [backend/scripts/README.md](backend/scripts/README.md).

```bash
# Backup
python backend/scripts/backup_postgres.py --output backups/ai.dump

# Restore (maintenance window)
python backend/scripts/restore_postgres.py --input backups/ai.dump --clean
```

Requires `postgresql-client` (`pg_dump` / `pg_restore`). Production image includes these tools.

## Monitoring

- Liveness: `GET /health`
- Readiness: `GET /ready` (also `/api/v1/ready`)
- Observability API: `GET /api/v1/observability/metrics`, `/traces`
- Structured logs with `trace_id`
- No Prometheus/Grafana required at this stage (foundation only)

## Security notes

- Set `SECURITY_ENABLED=true` in production
- Use API keys via `X-API-Key` (`POST /api/v1/security/keys`)
- Raw API keys are shown once; only hashes are stored
- Audit log: `GET /api/v1/security/audit`
- Rate limiting is in-memory (no Redis queue for limits yet)
- Keep Telegram/OpenRouter/MinIO secrets out of git

## CI

GitHub Actions (`.github/workflows/ci.yml`):

1. Install dependencies
2. Ruff lint (critical rules)
3. Pytest
4. Docker build of backend image

No automatic deployment.

## Документация

| Document | Description |
|----------|-------------|
| [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md) | Goals and principles |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Delivery roadmap |
| [docs/ADR/](docs/ADR/) | Architecture Decision Records |

## Принципы

- Нет жёстких keyword-сценариев
- Skills как расширяемые capabilities
- Memory / Knowledge / Workspace — отдельные слои
- Observability и Security — инфраструктура, не бизнес-логика

## Статус

Основной roadmap (этапы 1–24) доведён до production readiness foundation.

## Лицензия

Proprietary — внутренний проект маркетингового агентства.
