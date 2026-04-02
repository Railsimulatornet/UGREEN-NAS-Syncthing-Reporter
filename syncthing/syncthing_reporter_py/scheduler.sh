#!/bin/sh
set -eu

: "${RUN_AT:=08:00}"
: "${PRUNE_DAYS:=14}"
: "${REPORTER_BUILD_VERSION:=2026-03-17.1}"

APP_VERSION="v2"
APP_COPYRIGHT="Copyright Roman Glos 2026"

log() {
  printf "[scheduler] %s\n" "$*"
}

calc_target_epoch() {
  now=$(date +%s)
  tgt=$(date -d "today $RUN_AT" +%s 2>/dev/null || true)

  if [ -z "${tgt:-}" ]; then
    log "invalid RUN_AT value: $RUN_AT"
    exit 1
  fi

  if [ "$now" -ge "$tgt" ]; then
    date -d "tomorrow $RUN_AT" +%s
  else
    printf "%s\n" "$tgt"
  fi
}

log "syncthing_reporter_py ${APP_VERSION} | build ${REPORTER_BUILD_VERSION} | ${APP_COPYRIGHT}"

while :; do
  tgt=$(calc_target_epoch)
  now=$(date +%s)
  secs=$((tgt - now))

  if [ "$secs" -lt 0 ]; then
    secs=0
  fi

  log "next run at $(date -d "@$tgt" -Iseconds) (in ${secs}s)"
  sleep "$secs"

  echo "[run] $(date -Iseconds) start"
  python -u /app/report.py || echo "[run] failed ($?)"

  find /state/attach -type f -mtime +"$PRUNE_DAYS" -delete 2>/dev/null || true
  echo "[run] done"
done