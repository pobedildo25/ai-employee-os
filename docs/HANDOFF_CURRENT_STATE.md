# Handoff — NOVA / AI Employee OS (актуальное состояние)

Документ для передачи другому разработчику. Описывает **что реально есть сейчас**, а не только целевую архитектуру из `PROJECT_CONTEXT.md` / `ROADMAP.md` (они частично устарели).

Дата среза: **2026-07-16**.

---

## 1. Что это за продукт

**NOVA** — AI-сотрудник маркетингового агентства.

- Не keyword-бот и не набор кнопок.
- Агентный pipeline: Telegram → Executive Agent → plan / skills → artifacts.
- Основной канал: **Telegram long polling** (webhook в проде не используется).
- LLM только через **OpenRouter** (`LLMGateway`).
- Бренд в проде: `AGENT_NAME=NOVA`, DOCX с **HERALD** chrome.

Целевая модель (согласовано с заказчиком через grill):
полный продукт ≈ **реестр capabilities (~15) + Vision + локальный Whisper**, сдавать **кусками**, честно отказывать, если capability ещё нет.

---

## 2. Репозитории и ветки

| | |
|---|---|
| Writable fork | `github.com/pobedildo25/ai-employee-os` |
| Исторический origin / серверный клон | `dimoon528/NovaNova`, путь на сервере `~/NovaNova` |
| `main` | `6e94d3b` — auto-create business client (#1) |
| Активная ветка первого куска | `cursor/first-slice-alive-archive-1eba` @ `8b605c1` |
| PR первого куска | **[#10](https://github.com/pobedildo25/ai-employee-os/pull/10)** (DRAFT) |

### Открытые / связанные PR (не смержены, кроме #1)

| PR | Тема | Статус |
|----|------|--------|
| #1 | Business client auto-create | **MERGED** |
| #2 | Phase A agency profile / memory | DRAFT |
| #3 | Phase B multimodality (files / vision / voice) | DRAFT — **сюда смотреть для Vision/Whisper** |
| #4 | NovaNova baseline port | OPEN |
| #5 | P0/P1 architecture findings | DRAFT |
| #6 | P2 UX plan/progress/learning | DRAFT |
| #7 | P2 stabilization | DRAFT |
| #8 | HERALD DOCX (отдельная ветка) | DRAFT (часть уже в #10) |
| #9 | Cursor agent skills pack | DRAFT |
| #10 | First slice: living bot UX | DRAFT — **текущая линия работы** |

Коммиты #10 поверх `main`:
1. `2f9ff01` First slice: presence UX, LLM caps, live research, archive watcher  
2. `3074b98` HERALD DOCX chrome  
3. `70e7bdd` compose archive mount  
4. `381e107` never stuck on «Смотрю…»  
5. `2b41bf8` local greeting / FX without LLM  
6. `8b605c1` status только на реальных задачах  

---

## 3. Прод (живой Telegram)

| | |
|---|---|
| Host | `78.17.68.233` |
| SSH | user `admin` (в cloud-агентах: `DEPLOY_SSH_HOST/USER/PASSWORD`) |
| Live app dir | **`/home/admin/NovaNova`** |
| Compose | `docker compose` из `~/NovaNova/docker-compose.yml` (**не** `docker-compose.prod.yml`) |
| Backend | container `ai-employee-backend`, port `8000`, health OK |
| Deps | postgres `:5433`, redis `:6380`, qdrant `:6335`, minio `:9000` |
| Архив клиентов (host) | `/home/admin/business-assistant/user_data/clients` → mount `/data/agency_archive:ro` |
| Старый клон | `/home/admin/ai-employee-os` — скрипты деплоя смотрят сюда по умолчанию, **но Telegram сейчас крутится из NovaNova** |

### Важные env на проде

| Var | Значение / смысл |
|-----|------------------|
| `TELEGRAM_ENABLED` | `true` (polling активен) |
| `OPENROUTER_API_KEY` | задан, но часто **402 Insufficient credits** |
| `DEFAULT_LLM_MODEL` | `openai/gpt-4o-mini` |
| `HEAVY_LLM_MODEL` | `anthropic/claude-sonnet-4` |
| `LLM_MAX_TOKENS` / `LLM_HEAVY_MAX_TOKENS` | `4096` / `8192` |
| `RESEARCH_ONLINE_ENABLED` | `true` |
| `RESEARCH_ONLINE_MODEL` | `perplexity/sonar` |
| `AGENCY_ARCHIVE_WATCH_ENABLED` | **`false`** (выключен после сжигания кредитов) |
| `AGENCY_ARCHIVE_PATH` | `/data/agency_archive` |
| `APP_ENV` | сейчас `development` (технический долг) |

### Рассинхрон prod ↔ git tip (критично знать)

- Серверный git tip формально `3074b98`, ветка `deploy/first-slice-1eba`.
- Hotfix’ы после HERALD (**local replies, gateway 402, no «Смотрю» на чат**) заливалась **копированием файлов + rebuild образа**, не чистым git pull.
- На сервере дерево **грязное** (`flow.py`, `presenter.py`, `local_replies.py`, `gateway.py`, …).
- **Первый шаг новому разрабочику:** сверить файлы в контейнере с `8b605c1` / привести `~/NovaNova` к чистому tip ветки #10 и пересобрать.

Проверка в контейнере:
```bash
docker compose exec backend python -c "from app.adapters.telegram.local_replies import maybe_local_reply; from app.adapters.telegram import presenter; print(presenter.format_progress_header())"
```
Ожидаемо: есть `local_replies`, header = `Работаю над задачей…`.

---

## 4. Согласованный порядок доставки (grill)

1. Presence / живой бот  
2. Research / ответы  
3. Archive index + watcher  
4. Restart prod  
5. **Vision**  
6. **Local Whisper**  
7. Остальные capabilities  

Первый кусок (п.1–4) **в основном сделан в коде #10**, с оговорками ниже.

---

## 5. Что сделано (работает в коде / на проде с оговорками)

### Telegram UX
- Long polling поднимается в lifespan (`main.py` → `TelegramPollingService`).
- Chat vs task: Executive `RESPOND` / `ASK_CLARIFICATION` vs `CREATE_PLAN` / `EXECUTE`.
- **Простой чат:** ответ сразу новым сообщением, **без** «Смотрю…».
- **Реальная задача:** статус `Работаю над задачей…` + edit progress.
- Локальные ответы без LLM: приветствия + курс доллара ЦБ (`local_replies.py`).
- Честный отказ на фото / voice / unsupported media (`status_copy.py` + `dispatcher.py`).
- Approval / cancel / revise / retry клавиатуры — в коде и тестах.

### LLM
- Единый `LLMGateway` + OpenRouter provider.
- Cheap default + heavy model через `metadata.use_heavy_model`.
- Caps: `llm_max_tokens` / `llm_heavy_max_tokens`.
- Fail-fast на 402/auth (без бессмысленного перебора fallback-моделей).
- Честный текст `LLM_UNAVAILABLE`, если модель недоступна.

### Research
- Live provider `OpenRouterOnlineProvider` (Sonar) подключён.
- Mock research отключён на проде (`RESEARCH_ALLOW_MOCK=false`).
- **Без кредитов OpenRouter research фактически мёртв.**

### Agency archive
- Ingest per-client (`agency_archive/ingest.py`).
- Watcher с backoff на 402 (`watcher.py`).
- Compose mount host → `/data/agency_archive`.
- На проде watcher **выключен**, пока нет стабильных кредитов.

### Документы / skills
- Pipeline документов / презентаций / strategy / quality / revision — в коде.
- HERALD Word chrome на DOCX.
- Capability registry: document_analysis, brand_style, document_creation, presentation_design, strategy, client_intelligence, analytics, research, document_render, quality_review, revision, knowledge_migration, document, analysis, file.

### Инфра
- FastAPI, Alembic, Postgres, Redis, Qdrant, MinIO.
- `/health`, `/ready`.
- CI: ruff + pytest + docker build (`.github/workflows/ci.yml`).

---

## 6. Что НЕ сделано / заблокировано

| Тема | Статус |
|------|--------|
| Общий LLM-чат / задачи на проде | **Blocked**: OpenRouter 402 (нет кредитов) |
| Live research на проде | **Blocked** теми же кредитами |
| Archive watcher в проде | Код есть, **выключен** |
| Vision (фото/сканы) | **Не в этой ветке**. Честный decline. Смотреть **PR #3** |
| Whisper / расшифровка звонков | **Не в этой ветке**. Decline + env placeholders. Цель: **локальный** Whisper. PR #3 |
| Mem0 long-term memory | Placeholder в `.env.example`, в `Settings` нет |
| Frontend / admin panel | Пустой placeholder |
| Telegram webhook | Не прод-путь |
| Чистый prod compose / `APP_ENV=production` | Не доведено |
| Merge #10 в `main` | Ещё DRAFT |

---

## 7. Известные баги и долги

1. **Кредиты OpenRouter** — корневая причина «бот не отвечает умно». Сначала пополнить / сменить ключ.
2. **Watcher жёг кредиты** на ingest — держать `AGENCY_ARCHIVE_WATCH_ENABLED=false` до стабильного баланса.
3. **История UX «Смотрю…»** — на каждое сообщение ломало восприятие; сейчас статус только на задачах. Не возвращать presence на простой чат.
4. **Bot token светится в логах** (`getUpdates` URL). Ротировать токен.
5. **Split-brain deploy**: `NovaNova` (live) vs `ai-employee-os` (scripts default) vs GitHub tip.
6. Тест, который может быть красным после UX-смены:  
   `tests/test_telegram_production_stabilization.py::test_clarification_then_answer_resumes_task_pipeline`  
   (ожидает edit «Смотрю…» на clarification — поведение изменилось).
7. `docs/ROADMAP.md` чекбоксы сильно отстают от кода — не ориентироваться на них как на source of truth.
8. Не коммитить секреты (OpenRouter / Telegram / Context7 ключи из чатов).

---

## 8. Ключевые файлы

| Файл | Зачем |
|------|--------|
| `backend/app/main.py` | lifespan: watcher + telegram polling |
| `backend/app/core/config.py` | все env |
| `backend/app/adapters/telegram/flow.py` | продукт UX: chat/task/local/status |
| `backend/app/adapters/telegram/local_replies.py` | привет / курс без LLM |
| `backend/app/adapters/telegram/polling.py` | прод-транспорт |
| `backend/app/adapters/telegram/dispatcher.py` | media declines |
| `backend/app/adapters/telegram/progress.py` | edit одного progress-сообщения |
| `backend/app/ux/status_copy.py` | тексты статусов / ошибок / unsupported |
| `backend/app/llm/gateway.py` | caps, heavy routing, 402 fail-fast |
| `backend/app/agency_archive/*` | ingest + watcher |
| `backend/app/research/providers/openrouter_online_provider.py` | live research |
| `backend/app/skills/registry.py` | список skills |
| `backend/app/document_renderer/herald_chrome.py` | HERALD DOCX |
| `docker-compose.yml` | то, чем реально крутят NovaNova |
| `docs/PROJECT_CONTEXT.md` | целевое видение (не = текущий статус) |
| `docs/ARCHITECTURE.md` | целевая архитектура |

---

## 9. Как запускать / тестировать

```bash
# локально
cd backend
pip install -r requirements.txt   # или uv
ruff check app tests scripts
pytest -q

# точечно по Telegram UX первого куска
pytest tests/test_first_slice_presence_archive.py \
       tests/test_telegram_chat_vs_task.py \
       tests/test_telegram_product_ux.py \
       tests/e2e/test_scenario_05_telegram.py -q
```

Прод (осторожно):
```bash
ssh admin@78.17.68.233
cd ~/NovaNova
docker compose ps
docker compose logs --tail=200 backend
# после обновления кода:
docker compose build backend && docker compose up -d backend
```

---

## 10. Рекомендуемый следующий порядок работ

1. **Пополнить OpenRouter** и проверить в Telegram: обычный вопрос + research-запрос.  
2. **Синхронизировать прод** с tip `cursor/first-slice-alive-archive-1eba` (`8b605c1+`), убрать грязное дерево, один источник правды для деплоя.  
3. **Ротировать Telegram bot token** (уже был в логах).  
4. Починить/обновить clarification-тест под новый UX.  
5. Merge или довести **PR #10**.  
6. Включить `AGENCY_ARCHIVE_WATCH_ENABLED` только после стабильных кредитов; прогнать ingest на `user_data/clients`.  
7. Следующий продуктовый кусок по grill: **Vision** (честно, с download из Telegram) → затем **локальный Whisper**. Брать задел из **PR #3**, не изобретать параллельно.  
8. Не ломать работающие пути «ради красоты»: простые сообщения — без fake thinking status.

---

## 11. UX-правила, которые уже согласовали с заказчиком

- На `привет` / курс / простой ответ — **сразу ответ**, без «Смотрю» / «Думаю».
- Статус «работаю / прогресс» — **только** когда реально идёт задача (plan/execute).
- Нет capability → **честный отказ**, а не притворство.
- FX: лучше честный источник (сейчас ЦБ), чем галлюцинация модели.
- Не выкатывать фичи, которые молча жгут кредиты в фоне (watcher) без контроля.

---

## 12. Короткий TL;DR для нового разработчика

> Код первого куска живого бота — ветка/PR **#10**. Прод крутится в **`~/NovaNova`** на `78.17.68.233`. Без кредитов OpenRouter умный чат мёртв; привет и курс ЦБ работают локально. Watcher архива выключен. Vision/Whisper ещё нет (decline + задел в PR #3). Следующий осмысленный шаг: кредиты → чистый sync tip на прод → Vision → local Whisper. Не возвращать «Смотрю…» на каждый чих.
