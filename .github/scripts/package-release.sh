#!/usr/bin/env bash
# Package tracked release files without local configuration or runtime data.
set -Eeuo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
OUT="${1:?usage: package-release.sh OUTPUT_DIRECTORY}"
mkdir -p "$OUT"
OUT="$(realpath "$OUT")"
VERSION="$(tr -d '\r\n' < VERSION)"
[[ "$VERSION" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]
MANUAL='UGREEN_Syncthing_Reporter_Handbuch_DE-EN.pdf'
ZIP="syncthing-reporter-DE_EN_v${VERSION}.zip"
[[ -s "$MANUAL" && -s .github/release-title.txt && -s .github/release-notes.md ]]
grep -Fq "v$VERSION" .github/release-title.txt
# Reject tracked deployment data instead of accidentally shipping it.
while IFS= read -r -d '' path; do
  case "$path" in
    */.env|*/.env.*|*.env|*/state/*|*/attach/*|*/__pycache__/*)
      [[ "$path" == syncthing/.env.example ]] || {
        printf 'Refusing to package deployment data: %s\n' "$path" >&2
        exit 1
      } ;;
  esac
done < <(git ls-files -z -- syncthing)
git archive --format=zip --output="$OUT/$ZIP" HEAD -- \
  README.md LICENSE CHANGELOG.md VERSION Screens syncthing "$MANUAL"
cp -- "$MANUAL" "$OUT/$MANUAL"
cp -- .github/release-title.txt "$OUT/release-title.txt"
cp -- .github/release-notes.md "$OUT/release-notes.md"
printf '%s\n' "$VERSION" > "$OUT/version.txt"
# Validate the ZIP, including hidden example files, and preserve the handbook bytes.
python3 - "$OUT/$ZIP" "$OUT/$MANUAL" "$VERSION" <<'PY'
from pathlib import Path
import sys
import zipfile
archive, handbook, version = sys.argv[1:]
with zipfile.ZipFile(archive) as bundle:
    assert bundle.testzip() is None
    required = ('syncthing/.env.example', 'syncthing/docker-compose.yaml',
                'syncthing/docker-compose.local-build.yaml', 'README.md',
                'LICENSE', 'CHANGELOG.md', 'VERSION', Path(handbook).name)
    for name in required:
        assert name in bundle.namelist(), f'Missing release file: {name}'
    assert bundle.read('VERSION').decode().strip() == version
    assert bundle.read(Path(handbook).name) == Path(handbook).read_bytes()
    assert not any(name.startswith(('.git/', '.github/')) for name in bundle.namelist())
print('Release ZIP and unchanged handbook: OK')
PY
(cd "$OUT" && sha256sum "$ZIP" "$MANUAL" > SHA256SUMS)
printf 'Release package prepared: %s\n' "$ZIP"
