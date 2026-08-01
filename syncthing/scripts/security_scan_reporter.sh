#!/bin/sh
set -eu

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$PROJECT_DIR"

SERVICE_NAME="${REPORTER_SERVICE_NAME:-syncthing_reporter_py}"
OUTDIR="${REPORTER_SECURITY_OUTDIR:-./syncthing_reporter_py/state/security}"
STAMP="$(date +%Y%m%d_%H%M%S)"
TRIVY_IMAGE="${TRIVY_IMAGE:-aquasec/trivy:latest}"

mkdir -p "$OUTDIR"

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

CONTAINER_ID="$($COMPOSE ps -q "$SERVICE_NAME" 2>/dev/null || true)"
if [ -z "$CONTAINER_ID" ]; then
  echo "ERROR: reporter container is not running: $SERVICE_NAME"
  exit 1
fi

IMAGE_REF="$(docker inspect --format '{{.Config.Image}}' "$CONTAINER_ID")"

echo "[info] Scanning image: $IMAGE_REF"
echo "[info] Output directory: $OUTDIR"

docker run --rm       -v /var/run/docker.sock:/var/run/docker.sock       -v "$PROJECT_DIR/$OUTDIR:/out"       "$TRIVY_IMAGE" image       --scanners vuln       --severity HIGH,CRITICAL       --format json       --output "/out/trivy_syncthing_reporter_${STAMP}.json"       "$IMAGE_REF"

docker run --rm       -v /var/run/docker.sock:/var/run/docker.sock       -v "$PROJECT_DIR/$OUTDIR:/out"       "$TRIVY_IMAGE" image       --scanners vuln       --severity HIGH,CRITICAL       --format table       --output "/out/trivy_syncthing_reporter_${STAMP}_all.txt"       "$IMAGE_REF"

docker run --rm       -v /var/run/docker.sock:/var/run/docker.sock       -v "$PROJECT_DIR/$OUTDIR:/out"       "$TRIVY_IMAGE" image       --scanners vuln       --severity HIGH,CRITICAL       --ignore-unfixed       --format table       --output "/out/trivy_syncthing_reporter_${STAMP}_fixable.txt"       "$IMAGE_REF"

cat > "$OUTDIR/README_LAST_SCAN.txt" <<EOT
Syncthing Reporter security scan
Image: $IMAGE_REF
Timestamp: $STAMP

Files:
- trivy_syncthing_reporter_${STAMP}.json
- trivy_syncthing_reporter_${STAMP}_all.txt
- trivy_syncthing_reporter_${STAMP}_fixable.txt
EOT

echo "[done] Security scan finished."
echo "[done] Results written to: $OUTDIR"
