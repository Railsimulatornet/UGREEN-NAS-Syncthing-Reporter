#!/bin/sh
set -eu

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$PROJECT_DIR"

SERVICE_NAME="syncthing_reporter_py"
IMAGE_NAME="syncthing_reporter_py"
NEW_VERSION="${1:-2.2.0}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.local-build.yaml}"

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
echo "[info] Compose file: $COMPOSE_FILE"
echo "[info] Service: $SERVICE_NAME"
echo "[info] New reporter build version: $NEW_VERSION"

echo "[step] Stopping reporter service if it is running..."
$COMPOSE -f "$COMPOSE_FILE" stop "$SERVICE_NAME" >/dev/null 2>&1 || true

echo "[step] Removing old local reporter images..."
docker images --format '{{.Repository}}:{{.Tag}} {{.ID}}'       | awk -v img="$IMAGE_NAME" '$1 ~ "^" img ":" {print $2}'       | sort -u       | while read -r image_id; do
      [ -n "$image_id" ] && docker rmi -f "$image_id" >/dev/null 2>&1 || true
    done

echo "[step] Rebuilding reporter image with current base image..."
REPORTER_BUILD_VERSION="$NEW_VERSION"     REPORTER_VERSION="V2.2"     REPORTER_BUILD_DATE="2026-05-21"     $COMPOSE -f "$COMPOSE_FILE" build --pull --no-cache "$SERVICE_NAME"

echo "[step] Starting reporter service..."
REPORTER_BUILD_VERSION="$NEW_VERSION"     REPORTER_VERSION="V2.2"     REPORTER_BUILD_DATE="2026-05-21"     $COMPOSE -f "$COMPOSE_FILE" up -d --force-recreate "$SERVICE_NAME"

echo "[step] Reporter container status:"
$COMPOSE -f "$COMPOSE_FILE" ps "$SERVICE_NAME" || true

echo "[done] Reporter image has been rebuilt and restarted."
