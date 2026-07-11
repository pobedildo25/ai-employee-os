#!/bin/sh
set -e

# Production startup: optional Alembic migrations before serving traffic.
if [ "${RUN_MIGRATIONS_ON_STARTUP:-false}" = "true" ]; then
  echo "Running database migrations (alembic upgrade head)..."
  alembic upgrade head
  echo "Migrations complete."
fi

exec "$@"
