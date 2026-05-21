#!/bin/sh
set -eu

: "${RUN_AT:=08:00}"
: "${PRUNE_DAYS:=14}"
: "${REPORTER_VERSION:=V2.2}"
: "${REPORTER_BUILD_DATE:=2026-05-21}"
: "${REPORTER_BUILD_VERSION:=2026-05-21.5}"

APP_COPYRIGHT="Copyright Roman Glos 2026"

log() {
  printf '[scheduler] %s\n' "$*"
}

seconds_until_next_run() {
  python - "$RUN_AT" <<'PY'
import sys
from datetime import datetime, timedelta

run_at = sys.argv[1].strip()
try:
    hour_s, minute_s = run_at.split(":", 1)
    hour = int(hour_s)
    minute = int(minute_s)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError
except Exception:
    print("ERROR: RUN_AT must use HH:MM format, for example 08:00", file=sys.stderr)
    sys.exit(2)

now = datetime.now()
target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
if target <= now:
    target += timedelta(days=1)

seconds = int((target - now).total_seconds())
print(f"{seconds}|{target.isoformat()}")
PY
}

log "syncthing_reporter_py ${REPORTER_VERSION} | build_date ${REPORTER_BUILD_DATE} | build ${REPORTER_BUILD_VERSION} | ${APP_COPYRIGHT}"

while :; do
  schedule_info=$(seconds_until_next_run)
  secs=${schedule_info%%|*}
  target_iso=${schedule_info#*|}
  log "next run at ${target_iso} (in ${secs}s)"
  sleep "$secs"
  echo "[run] $(date -Iseconds) start"
  python -u /app/report.py || echo "[run] failed ($?)"
  find /state/attach -type f -mtime +"$PRUNE_DAYS" -delete 2>/dev/null || true
  echo "[run] done"
done
