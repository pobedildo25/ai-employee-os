#!/usr/bin/env bash
# Rollback production backend to a previous image tag (no rebuild).
#
# Usage (from repo root):
#   ./deploy/rollback.sh                         # interactive: pick from local images
#   ROLLBACK_IMAGE=ai-employee-os-backend:prod-<sha> ./deploy/rollback.sh
#
# Then restarts compose with the retagged :prod image (no --build).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"
PROD_TAG="ai-employee-os-backend:prod"

list_images() {
  echo "Recent local images matching ai-employee-os-backend:"
  docker images --format 'table {{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.CreatedSince}}' \
    | head -n 1
  docker images --format '{{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.CreatedSince}}' \
    | grep -E '^ai-employee-os-backend:' \
    | head -n 20 \
    || echo "(none found)"
}

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE" >&2
  exit 1
fi

TARGET="${ROLLBACK_IMAGE:-}"

if [ -z "$TARGET" ]; then
  list_images
  echo
  echo "Set ROLLBACK_IMAGE=ai-employee-os-backend:prod-<sha> or enter a tag below."
  read -r -p "ROLLBACK_IMAGE: " TARGET
fi

if [ -z "$TARGET" ]; then
  echo "ROLLBACK_IMAGE is required" >&2
  exit 1
fi

if ! docker image inspect "$TARGET" >/dev/null 2>&1; then
  echo "Image not found locally: $TARGET" >&2
  exit 1
fi

echo "Retagging $TARGET -> $PROD_TAG"
docker tag "$TARGET" "$PROD_TAG"

echo "Starting stack without rebuild..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d

echo "Waiting for /ready..."
for i in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:${API_PORT:-8000}/ready" >/dev/null 2>&1; then
    echo "READY_OK"
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
    exit 0
  fi
  sleep 3
done

echo "WARNING: /ready did not succeed within timeout; check compose logs" >&2
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
exit 1
