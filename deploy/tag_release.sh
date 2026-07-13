#!/usr/bin/env bash
# Tag the current prod backend image with the short git SHA for rollback.
# Usage (from repo root, after build):
#   ./deploy/tag_release.sh
#   IMAGE=ai-employee-os-backend:prod ./deploy/tag_release.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SOURCE_IMAGE="${IMAGE:-ai-employee-os-backend:prod}"
SHA="$(git rev-parse --short HEAD)"
TAGGED="ai-employee-os-backend:prod-${SHA}"

if ! docker image inspect "$SOURCE_IMAGE" >/dev/null 2>&1; then
  echo "Image not found: $SOURCE_IMAGE (build first)" >&2
  exit 1
fi

docker tag "$SOURCE_IMAGE" "$TAGGED"
echo "Tagged $SOURCE_IMAGE -> $TAGGED"
echo "Record this tag for rollback: ROLLBACK_IMAGE=$TAGGED"
