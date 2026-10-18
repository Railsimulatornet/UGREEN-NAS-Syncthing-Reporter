#!/bin/sh
set -eu

PROJECT_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$PROJECT_DIR"

SERVICE_NAME="syncthing_reporter_py"
if [ -f "$PROJECT_DIR/../VERSION" ]; then
  RELEASE_VERSION="$(tr -d '\r\n' < "$PROJECT_DIR/../VERSION")"
else
  # The documented NAS installation copies only the syncthing directory.
  RELEASE_VERSION="$(sed -n 's/^ARG REPORTER_VERSION=V//p' "$PROJECT_DIR/syncthing_reporter_py/Dockerfile" | tr -d '\r')"
fi
if ! printf '%s\n' "$RELEASE_VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "ERROR: Reporter release version was not found or is invalid." >&2
  exit 1
fi
NEW_VERSION="${1:-$RELEASE_VERSION}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.local-build.yaml}"

case "$NEW_VERSION" in
  ''|[.-]*|*[!a-zA-Z0-9_.-]*)
    echo "ERROR: Build version must be a valid Docker image tag." >&2
    exit 1
    ;;
esac
if [ "${#NEW_VERSION}" -gt 128 ]; then
  echo "ERROR: Build version must not exceed 128 characters." >&2
  exit 1
fi

export REPORTER_VERSION="V$RELEASE_VERSION"
export REPORTER_BUILD_VERSION="$NEW_VERSION"
export REPORTER_BUILD_DATE="${REPORTER_BUILD_DATE:-$(date -u +%Y-%m-%d)}"

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

echo "[step] Rebuilding reporter image with current base image..."
$COMPOSE -f "$COMPOSE_FILE" build --pull --no-cache "$SERVICE_NAME"

echo "[step] Recreating reporter service with the successful build..."
$COMPOSE -f "$COMPOSE_FILE" up -d --no-deps --force-recreate "$SERVICE_NAME"

echo "[step] Reporter container status:"
$COMPOSE -f "$COMPOSE_FILE" ps "$SERVICE_NAME" || true

echo "[done] Reporter image has been rebuilt and restarted."
