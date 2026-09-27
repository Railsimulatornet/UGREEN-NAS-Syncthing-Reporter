#!/usr/bin/env bash
# Scan an OCI layout or Docker archive. Any tooling failure blocks publication.
set -Eeuo pipefail

IMAGE_INPUT="$(realpath "${1:?usage: scan-image.sh IMAGE_INPUT REPORT_DIR}")"
OUTDIR="${2:?usage: scan-image.sh IMAGE_INPUT REPORT_DIR}"
TRIVY_IMAGE="${TRIVY_IMAGE:-ghcr.io/aquasecurity/trivy:latest}"
CACHE="${TRIVY_CACHE_DIR:-${RUNNER_TEMP:-/tmp}/reporter-trivy-cache}"
if [[ -d "$IMAGE_INPUT" ]]; then
  [[ -s "$IMAGE_INPUT/index.json" && -s "$IMAGE_INPUT/oci-layout" ]]
else
  [[ -f "$IMAGE_INPUT" && -s "$IMAGE_INPUT" ]]
fi
mkdir -p "$OUTDIR" "$CACHE"
OUTDIR="$(realpath "$OUTDIR")"
CACHE="$(realpath "$CACHE")"

trivy() {
  docker run --rm \
    --mount "type=bind,src=$IMAGE_INPUT,dst=/image,readonly" \
    --mount "type=bind,src=$OUTDIR,dst=/out" \
    --mount "type=bind,src=$CACHE,dst=/root/.cache/trivy" \
    "$TRIVY_IMAGE" "$@"
}

# Preserve all severities and unfixed findings in the machine-readable report.
trivy image --input /image --platform linux/amd64 \
  --scanners vuln --pkg-types os,library --no-progress \
  --format json --output /out/syncthing_reporter_trivy.json
[[ -s "$OUTDIR/syncthing_reporter_trivy.json" ]]

trivy convert --format sarif --severity HIGH,CRITICAL \
  --output /out/syncthing_reporter_trivy.sarif /out/syncthing_reporter_trivy.json
trivy convert --format table --scanners vuln --severity HIGH,CRITICAL \
  --output /out/syncthing_reporter_trivy_all.txt /out/syncthing_reporter_trivy.json

# Reuse this run's database and image; do not hide status=fixed findings.
# 42 = actionable vulnerabilities; 43 = OS EOL; other nonzero = tooling error.
if trivy image --input /image --platform linux/amd64 \
  --scanners vuln --pkg-types os,library --no-progress --skip-db-update \
  --severity HIGH,CRITICAL --ignore-unfixed --exit-code 42 --exit-on-eol 43 \
  --format table --output /out/syncthing_reporter_trivy_fixable.txt; then
  cat "$OUTDIR/syncthing_reporter_trivy_fixable.txt"
else
  rc=$?
  if [[ -f "$OUTDIR/syncthing_reporter_trivy_fixable.txt" ]]; then
    cat "$OUTDIR/syncthing_reporter_trivy_fixable.txt"
  fi
  printf 'Security gate failed (exit code %s).\n' "$rc" >&2
  exit "$rc"
fi
