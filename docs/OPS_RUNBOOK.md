# Operations Runbook — AI Employee OS (production)

Operational procedures for Sprint D hardening. Secrets stay in `.env.production` (never commit).

## Stack basics

```bash
cp .env.production.example .env.production
# fill secrets
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

Recommended after each build: tag the image for rollback (see Release / Rollback).

One-shot migrations (scaled API):

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production run --rm backend \
  python /app/docker/migrate_with_lock.py
# then RUN_MIGRATIONS_ON_STARTUP=false on API replicas
```

---

## TLS at edge (profile `tls`)

Default prod compose publishes HTTP on `${API_PORT:-8000}`. Optional nginx terminator is under Compose profile `tls` (service `edge`).

### Enable

1. Place certificates:
   - Default: `./deploy/certs/fullchain.pem` and `./deploy/certs/privkey.pem`
   - Or set host paths via env (see `.env.production.example`):
     - `TLS_CERT_PATH` / `TLS_KEY_PATH` — copied or symlinked into `./deploy/certs/` before up, **or**
     - `TLS_CERTS_DIR` — directory mounted read-only at `/etc/nginx/certs` (must contain `fullchain.pem` + `privkey.pem`)
   - Let's Encrypt: set `TLS_CERTS_DIR=/etc/letsencrypt/live/YOUR_DOMAIN` only if those filenames match, or adjust `deploy/nginx/nginx.conf` to the live paths and mount `/etc/letsencrypt`.

2. Review `deploy/nginx/nginx.conf` (example: `deploy/nginx/nginx.conf.example`).

3. Start with the profile:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production --profile tls up -d
```

Edge publishes `443` (and `80` for redirect). Nginx proxies `https://:443` → `backend:8000` on the internal network.

### Do not expose backend `:8000` publicly when using TLS

When the `tls` profile is active, operators should **not** leave the API reachable on the public internet:

- Prefer binding the API only to localhost, e.g. in `.env.production`:
  `API_HOST_BIND=127.0.0.1`
- Or remove / comment the `backend.ports` mapping in an override and publish **only** `443` (and optionally `80`) via `edge`.

Default without TLS keeps `${API_HOST_BIND:-0.0.0.0}:${API_PORT:-8000}:8000` for hosts without certs.

---

## Backups schedule (profile `backup`)

Postgres logical dumps use `backend/scripts/backup_postgres.py` (already in the backend image under `/app/scripts/`).

### Compose loop (preferred)

Service `backup` runs `deploy/backup_loop.sh`: daily `pg_dump` into volume `backend_backups` (`/app/backups`), then deletes `*.dump` older than `BACKUP_RETENTION_DAYS` (default 14).

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production --profile backup up -d
```

Env (optional):

| Variable | Default | Meaning |
|----------|---------|---------|
| `BACKUP_RETENTION_DAYS` | `14` | Delete dumps older than N days |
| `BACKUP_INTERVAL_SECONDS` | `86400` | Sleep between runs |
| `BACKUP_DIR` | `/app/backups` | Output directory |

Combine profiles as needed:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production --profile tls --profile backup up -d
```

### Host crontab alternative

One-shot dump (preferred for cron; the compose `backup` service already loops):

```cron
0 3 * * * cd /path/to/ai-employee-os && docker compose -f docker-compose.prod.yml --env-file .env.production run --rm --no-deps --entrypoint "" backup python /app/scripts/backup_postgres.py --output /app/backups/cron_$$(date -u +\%Y\%m\%d).dump
```

Or without the profile service, via backend:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production exec -T backend \
  python /app/scripts/backup_postgres.py --output /app/backups/manual.dump
```

Restore: `backend/scripts/restore_postgres.py` (see `backend/scripts/README.md`).

---

## Release / Rollback

### Tag each release

After build, keep a SHA-tagged image so rollback does not require rebuild:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production build
./deploy/tag_release.sh
# → ai-employee-os-backend:prod-<short-sha>
```

`deploy/release_on_server.py` also tags `prod-$(git rev-parse --short HEAD)` after build when run on the server.

### Rollback playbook

1. List recent local images: `./deploy/rollback.sh` (prints `ai-employee-os-backend:*`) or `docker images | grep ai-employee-os-backend`.
2. Choose previous tag, e.g. `ai-employee-os-backend:prod-abc1234`.
3. Retag to floating `:prod` and recreate containers **without rebuild**:

```bash
ROLLBACK_IMAGE=ai-employee-os-backend:prod-abc1234 ./deploy/rollback.sh
# equivalent:
# docker tag "$ROLLBACK_IMAGE" ai-employee-os-backend:prod
# docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

4. Confirm `/ready` and compose health. If migrations ran forward-only on a newer image, rolling back app code may require a DB restore from backup — plan releases accordingly.

Do **not** use `up -d --build` during rollback.

---

## Task queue / Celery

Celery is **not** used. Background work uses the internal Postgres-backed task queue (`app.task_queue`). Adding a broker is deferred until there are long-running jobs that need one.
