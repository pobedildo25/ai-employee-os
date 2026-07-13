# План запуска — NOVA (локально + проверка в Telegram)

**Дата:** 2026-07-13  
**Режим:** сначала локальный стек на машине разработчика, проверка диалогов в реальном Telegram.  
**Не цель этого документа:** открытый production для всех пользователей.

Связанные документы: `OPS_RUNBOOK.md`, `RELEASE_CANDIDATE_REPORT.md`, `PRODUCTION_CONTRACT.md`, `.env.example` / `.env.production.example`.

---

## Цель

1. Поднять backend + зависимости **локально** (Docker Compose).
2. Подключить **реального Telegram-бота** и прогнать smoke с аккаунтов из allowlist.
3. Только после успешного локального smoke — готовить staging/prod (`.env.production`, TLS, backups).

---

## Фаза 0 — Зафиксировать режим

1. Пилот = закрытый: 3–10 Telegram user id в allowlist.
2. Research:
   - **OFF** (безопаснее для первого локального прогона), или
   - **ON**: `RESEARCH_ENABLED=true`, `RESEARCH_PROVIDER=sonar`, модель `perplexity/sonar`.
3. Semantic memory: **OFF** (`SEMANTIC_MEMORY_ENABLED=false`).
4. Если research включаешь — не обещать в чате то, чего контракт ещё описывает как OFF (при необходимости обновить `PRODUCTION_CONTRACT.md`).

---

## Фаза 1 — Локальный env

Рекомендуемый путь для «локально + Telegram»:

```bash
cp .env.example .env
# заполнить секреты; файл не коммитить
```

Для pytest из `backend/` либо скопировать `.env` в `backend/.env`, либо запускать compose из корня (сервисы берут корневой env).

### Обязательно заполнить

| Переменная | Зачем |
|------------|--------|
| `OPENROUTER_API_KEY` | Реальный ключ (не `change-me`) |
| `TELEGRAM_BOT_TOKEN` | Токен от BotFather |
| `TELEGRAM_ENABLED=true` | Включить бота |
| `TELEGRAM_ALLOWED_USER_IDS` | Список id пилота, **не пустой** |

### Локальный профиль (отличие от prod)

| Переменная | Локально | Потом в prod |
|------------|----------|--------------|
| `APP_ENV` | `development` (или `production` только если осознанно тестируешь fail-closed) | `production` |
| `TELEGRAM_INLINE_POLLING` | `true` — polling в API-процессе, проще | `false` + отдельный telegram worker |
| `SECURITY_ENABLED` | можно `false` на первом прогоне | `true` |
| `APP_DEBUG` | можно `true` | `false` |

### Research (выбрать одно)

```env
# Вариант A — OFF
RESEARCH_ENABLED=false
RESEARCH_PROVIDER=none

# Вариант B — Sonar через OpenRouter
RESEARCH_ENABLED=true
RESEARCH_PROVIDER=sonar
RESEARCH_SONAR_MODEL=perplexity/sonar
```

```env
SEMANTIC_MEMORY_ENABLED=false
```

Postgres / Redis / MinIO / Qdrant — как в `.env.example` под `docker compose` (пароли можно оставить dev-значениями **только** локально).

---

## Фаза 2 — Поднять локальный стек

Из корня репозитория:

```bash
docker compose up -d --build
```

Дождаться healthy сервисов, затем:

```bash
curl -f http://localhost:8000/health
curl -f http://localhost:8000/ready
```

Ожидание: `/health` = 200; `/ready` — postgres/redis (и при наличии minio/qdrant) без critical fail.

Логи API / бота:

```bash
docker compose logs -f backend
```

Если Telegram polling встроен в API (`TELEGRAM_INLINE_POLLING=true`) — смотреть те же логи на апдейты бота.

---

## Фаза 3 — Smoke в Telegram (обязательно)

Писать боту **только** с аккаунта из `TELEGRAM_ALLOWED_USER_IDS`.

| # | Действие | Ожидание |
|---|----------|----------|
| 1 | `/start` или «Привет» | Один нормальный ответ, без traceback |
| 2 | Вопрос («Что такое SWOT?») | RESPOND, без плана и без лишнего «Думаю…» на пустом месте |
| 3 | «Сделай КП …» (с деталями) | EXECUTE → артефакт или осмысленный текст; **не** silent «Готово» без результата |
| 4 | После результата: «Сделай короче» | Правка / task через Executive, не мёртвый keyword-path |
| 5 | «Сделай что-нибудь» | ASK_CLARIFICATION |
| 6 | Аккаунт **вне** allowlist | Отказ в доступе |
| 7 | (если research ON) запрос с исследованием | Реальные источники / не mock_not_production |

Желательно: кратковременно остановить qdrant → задача всё равно доходит до ответа пользователю.

**Пользователей пилота не расширять**, пока пункты 1–6 не зелёные.

---

## Фаза 4 — Чеклист Go / No-go (локальный pilot)

**Go**, если:

- [ ] `.env` с реальными OpenRouter + Telegram token  
- [ ] Allowlist не пустой  
- [ ] `docker compose` поднят, `/health` и `/ready` ок  
- [ ] Telegram smoke 1–6 пройден  
- [ ] Research/semantic соответствуют решению фазы 0  

**No-go**, если:

- [ ] placeholder ключи (`change-me`)  
- [ ] пустой allowlist при включённом боте в «жёстком» режиме  
- [ ] `/ready` падает на postgres/redis  
- [ ] traceback или silent «Готово» в чате  

---

## Фаза 5 — После локального успеха → staging/prod

Делать **только** когда фаза 3 закрыта.

1. `cp .env.production.example .env.production` — сильные пароли, `APP_ENV=production`, `APP_DEBUG=false`.
2. `TELEGRAM_INLINE_POLLING=false` + сервис telegram worker в `docker-compose.prod.yml`.
3. `SECURITY_ENABLED=true`, Redis AUTH, сильный `APP_SECRET_KEY`.
4. Миграции: one-shot из `OPS_RUNBOOK.md` или контролируемый `RUN_MIGRATIONS_ON_STARTUP`.
5. Подъём:
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
   ```
6. Повторить smoke из фазы 3 на staging.
7. Ops: profile `backup`; при внешнем доступе — profile `tls` (`OPS_RUNBOOK.md`); tag image для rollback.

---

## Порядок работ (кратко)

```
0. Режим + allowlist + research on/off
1. .env (локально) + ключи
2. docker compose up → /health /ready
3. Smoke в Telegram
4. Go/No-go локального pilot
5. .env.production + prod compose (когда 3–4 зелёные)
```

---

## Известные ограничения (не блокеры локального pilot)

- Semantic / embeddings — OFF до отдельного wiring (см. `ADR_RESEARCH_EMBEDDINGS.md`).
- PDF render — stub; не обещать PDF как готовый формат.
- Полный live Docker smoke на CI-хосте мог быть не прогнан — локальная фаза 2–3 это закрывает у оператора.
