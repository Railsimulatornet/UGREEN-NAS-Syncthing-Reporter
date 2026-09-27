#!/usr/bin/env bash
# Test OCI publication using a disposable loopback-only registry on a CI runner.
set -Eeuo pipefail

ARCHIVE="$(realpath "${1:?usage: test-image-promotion.sh OCI_ARCHIVE}")"
[[ -s "$ARCHIVE" ]]
WORK="$(mktemp -d)"
CID=''
cleanup() {
  if [[ -n "$CID" ]]; then docker rm -fv "$CID" >/dev/null 2>&1 || true; fi
  rm -rf -- "$WORK"
}
trap cleanup EXIT

CID="$(docker run --rm -d --publish 127.0.0.1::5000 \
  --env OTEL_TRACES_EXPORTER=none registry:3)"
ENDPOINT="$(docker port "$CID" 5000/tcp)"
[[ "$ENDPOINT" =~ ^127\.0\.0\.1:[0-9]+$ ]]
READY=0
for ((i=0; i<30; i++)); do
  if curl --fail --silent --show-error --max-time 2 \
    "http://$ENDPOINT/v2/" >/dev/null 2>&1; then READY=1; break; fi
  sleep 1
done
[[ "$READY" == 1 ]]

skopeo inspect --raw "oci-archive:$ARCHIVE" > "$WORK/expected.json"
EXPECTED="$(skopeo manifest-digest "$WORK/expected.json")"
TARGET="$ENDPOINT/syncthing-reporter:verified"
# Plain HTTP is confined to the disposable loopback-only test registry.
skopeo copy --all --preserve-digests --dest-tls-verify=false \
  --digestfile "$WORK/pushed.digest" "oci-archive:$ARCHIVE" "docker://$TARGET"
[[ "$(cat "$WORK/pushed.digest")" == "$EXPECTED" ]]
skopeo inspect --raw --tls-verify=false "docker://$TARGET" > "$WORK/registry.json"
cmp "$WORK/expected.json" "$WORK/registry.json"
# Read all child manifests and attestations back, not just the image index.
skopeo copy --all --preserve-digests --src-tls-verify=false \
  "docker://$TARGET" "oci:$WORK/roundtrip"
skopeo inspect --raw "oci:$WORK/roundtrip" > "$WORK/roundtrip.json"
cmp "$WORK/expected.json" "$WORK/roundtrip.json"
printf 'Registry round trip with unchanged image and attestations: OK (%s)\n' "$EXPECTED"
