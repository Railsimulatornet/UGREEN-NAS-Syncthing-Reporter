#!/bin/sh
set -eu

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$PROJECT_DIR"

SERVICE_NAME="syncthing_reporter_py"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker command not found."
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "ERROR: Docker Compose was not found."
  exit 1
fi

echo "[info] Project directory: $PROJECT_DIR"
echo "[step] Pulling current images..."
$COMPOSE pull "$SERVICE_NAME"

echo "[step] Restarting reporter service with the pulled image..."
$COMPOSE up -d --force-recreate "$SERVICE_NAME"

echo "[step] Reporter container status:"
$COMPOSE ps "$SERVICE_NAME" || true

echo "[done] Reporter image update finished."
