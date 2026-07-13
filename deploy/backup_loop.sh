#!/bin/sh
# Daily Postgres backup loop for compose service `backup` (profile: backup).
# Expects DATABASE_URL and pg_dump (backend image already has postgresql-client).
set -eu

BACKUP_DIR="${BACKUP_DIR:-/app/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
INTERVAL_SECONDS="${BACKUP_INTERVAL_SECONDS:-86400}"
SCRIPT="${BACKUP_SCRIPT:-/app/scripts/backup_postgres.py}"

mkdir -p "$BACKUP_DIR"

echo "backup_loop: dir=$BACKUP_DIR retention_days=$RETENTION_DAYS interval=${INTERVAL_SECONDS}s"

while true; do
  stamp="$(date -u +%Y%m%d_%H%M%S)"
  out="${BACKUP_DIR}/ai_employee_os_${stamp}.dump"
  echo "backup_loop: starting $out"
  if python "$SCRIPT" --output "$out"; then
    echo "backup_loop: ok $out"
  else
    echo "backup_loop: FAILED $out" >&2
  fi

  if [ "$RETENTION_DAYS" -gt 0 ] 2>/dev/null; then
    # Delete dumps older than retention (best-effort; portable find -mtime).
    find "$BACKUP_DIR" -type f -name '*.dump' -mtime "+${RETENTION_DAYS}" -print -delete 2>/dev/null \
      || true
  fi

  sleep "$INTERVAL_SECONDS"
done
