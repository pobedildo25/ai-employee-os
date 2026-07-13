#!/bin/sh
set -e

# Production startup: optional Alembic migrations under Postgres advisory lock.
# Prefer one-shot migrations for scaled APIs:
#   docker compose run --rm backend python /app/docker/migrate_with_lock.py
# and set RUN_MIGRATIONS_ON_STARTUP=false on API replicas.
if [ "${RUN_MIGRATIONS_ON_STARTUP:-false}" = "true" ]; then
  echo "Running database migrations with advisory lock..."
  python /app/docker/migrate_with_lock.py
  echo "Migrations complete."
fi

exec "$@"
