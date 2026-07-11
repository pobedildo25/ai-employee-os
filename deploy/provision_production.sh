#!/usr/bin/env bash
# Provision production stack on the server (run from repo root).
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/ai-employee-os}"
ARCHIVE_PATH="${AGENCY_ARCHIVE_PATH:-/home/admin/business-assistant/user_data/clients}"

cd "$REPO_DIR"

git fetch origin
git checkout main
git pull --ff-only origin main

if [ ! -f .env.production ]; then
  echo "Missing .env.production — create from .env.production.example first" >&2
  exit 1
fi

export AGENCY_ARCHIVE_PATH="$ARCHIVE_PATH"

docker compose -f docker-compose.prod.yml --env-file .env.production build
docker compose -f docker-compose.prod.yml --env-file .env.production up -d

echo "Waiting for backend readiness..."
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${API_PORT:-8000}/ready" >/dev/null 2>&1; then
    echo "Backend ready."
    break
  fi
  sleep 2
done

curl -fsS "http://127.0.0.1:${API_PORT:-8000}/health" || true
echo
curl -fsS "http://127.0.0.1:${API_PORT:-8000}/ready" || true
echo

docker compose -f docker-compose.prod.yml --env-file .env.production ps
