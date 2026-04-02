#!/bin/sh
set -eu
umask 002
: "${STATE_DIR:=/state}"
: "${ATTACH_DIR:=/state/attach}"
: "${REPORTER_VERSION:=V2}"
: "${REPORTER_BUILD_DATE:=2026-03-17}"
: "${REPORTER_COPYRIGHT:=Roman Glos 2026}"
mkdir -p "$ATTACH_DIR"
chown -R "$(id -u):$(id -g)" "$STATE_DIR" 2>/dev/null || true
chmod -R u+rwX,g+rwX "$STATE_DIR" 2>/dev/null || true
printf '[startup] syncthing_reporter_py | version=%s | build=%s | copyright=%s\n'   "$REPORTER_VERSION" "$REPORTER_BUILD_DATE" "$REPORTER_COPYRIGHT"
exec /app/scheduler.sh
