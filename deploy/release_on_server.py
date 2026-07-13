#!/usr/bin/env python3
"""One-shot production release on remote server. Secrets only from environment."""

from __future__ import annotations

import base64
import os
import secrets
import sys
import textwrap

from deploy.remote_ops import connect, run


def _req(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"Missing env: {name}", file=sys.stderr)
        sys.exit(1)
    return value


def main() -> int:
    openrouter_key = _req("DEPLOY_OPENROUTER_API_KEY")
    telegram_token = _req("DEPLOY_TELEGRAM_BOT_TOKEN")
    archive_path = os.environ.get(
        "DEPLOY_AGENCY_ARCHIVE_PATH",
        "/home/admin/business-assistant/user_data/clients",
    )
    repo_dir = os.environ.get("DEPLOY_REPO_DIR", "/home/admin/ai-employee-os")
    repo_url = os.environ.get(
        "DEPLOY_REPO_URL",
        "https://github.com/pobedildo25/ai-employee-os.git",
    )

    pg_pass = secrets.token_urlsafe(24)
    minio_access = secrets.token_urlsafe(16)
    minio_secret = secrets.token_urlsafe(32)
    app_secret = secrets.token_urlsafe(48)

    env_body = textwrap.dedent(
        f"""
        APP_ENV=production
        APP_DEBUG=false
        APP_SECRET_KEY={app_secret}
        API_HOST=0.0.0.0
        API_PORT=8000
        UVICORN_WORKERS=1
        RUN_MIGRATIONS_ON_STARTUP=true
        POSTGRES_DB=ai_employee_os
        POSTGRES_USER=ai_employee
        POSTGRES_PASSWORD={pg_pass}
        DATABASE_URL=postgresql+asyncpg://ai_employee:{pg_pass}@postgres:5432/ai_employee_os
        DB_POOL_SIZE=10
        DB_MAX_OVERFLOW=20
        DB_POOL_TIMEOUT=30
        DB_POOL_RECYCLE=1800
        REDIS_URL=redis://redis:6379/0
        QDRANT_URL=http://qdrant:6333
        QDRANT_COLLECTION=knowledge
        MINIO_ENDPOINT=minio:9000
        MINIO_ACCESS_KEY={minio_access}
        MINIO_SECRET_KEY={minio_secret}
        MINIO_SECURE=false
        MINIO_BUCKET=artifacts
        OPENROUTER_API_KEY={openrouter_key}
        OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
        DEFAULT_LLM_MODEL=anthropic/claude-sonnet-4
        FALLBACK_LLM_MODEL=openai/gpt-4o-mini
        TELEGRAM_BOT_TOKEN={telegram_token}
        TELEGRAM_ENABLED=true
        AGENT_NAME=NOVA
        SECURITY_ENABLED=true
        SECURITY_RATE_LIMIT=120
        SECURITY_RATE_WINDOW_SECONDS=60
        MEMORY_ENABLED=true
        SKILLS_ENABLED=true
        REDIS_MEMORY_TTL=3600
        LOG_LEVEL=INFO
        AGENCY_ARCHIVE_PATH={archive_path}
        """
    ).strip() + "\n"

    env_b64 = base64.b64encode(env_body.encode("utf-8")).decode("ascii")

    remote_script = textwrap.dedent(
        f"""
        set -e
        REPO_DIR="{repo_dir}"
        if [ ! -d "$REPO_DIR/.git" ]; then
          git clone "{repo_url}" "$REPO_DIR"
        fi
        cd "$REPO_DIR"
        git fetch origin
        git checkout main
        git pull --ff-only origin main
        python3 - <<'PY'
        import base64, pathlib
        data = base64.b64decode("{env_b64}")
        path = pathlib.Path(".env.production")
        path.write_bytes(data)
        path.chmod(0o600)
        print("wrote .env.production")
        PY
        export AGENCY_ARCHIVE_PATH="{archive_path}"
        docker compose -f docker-compose.prod.yml --env-file .env.production build
        SHA="$(git rev-parse --short HEAD)"
        docker tag ai-employee-os-backend:prod "ai-employee-os-backend:prod-${{SHA}}"
        echo "Tagged ai-employee-os-backend:prod-${{SHA}} (rollback: ROLLBACK_IMAGE=...)"
        docker compose -f docker-compose.prod.yml --env-file .env.production up -d
        echo '--- compose ps ---'
        docker compose -f docker-compose.prod.yml --env-file .env.production ps
        for i in $(seq 1 40); do
          if curl -fsS http://127.0.0.1:8000/ready >/dev/null 2>&1; then
            echo READY_OK
            break
          fi
          sleep 3
        done
        curl -fsS http://127.0.0.1:8000/health || true
        echo
        curl -fsS http://127.0.0.1:8000/ready || true
        echo
        docker compose -f docker-compose.prod.yml --env-file .env.production exec -T backend alembic current || true
        docker compose -f docker-compose.prod.yml --env-file .env.production exec -T backend python scripts/ingest_agency_archive.py --archive-root /data/agency_archive --agency-name "NOVA Agency" --max-files 120 || true
        docker compose -f docker-compose.prod.yml --env-file .env.production exec -T backend python scripts/backup_postgres.py --output backups/prod_smoke_backup.dump
        docker compose -f docker-compose.prod.yml --env-file .env.production logs --tail 40 backend
        """
    ).strip()

    client = connect()
    try:
        code, out, err = run(client, remote_script, timeout=1800)
        safe_out = out.replace(openrouter_key, "***").replace(telegram_token, "***")
        safe_err = err.replace(openrouter_key, "***").replace(telegram_token, "***")
        print(safe_out)
        if safe_err.strip():
            print(safe_err, file=sys.stderr)
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
