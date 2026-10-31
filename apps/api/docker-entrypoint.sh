#!/bin/sh
set -eu
# Render mounts the persistent disk as root. Chown it, then drop to uid 10001.
if [ "$(id -u)" = "0" ]; then
  mkdir -p "${NIYAM_BLOB_DIR:-/data/var/blobs}"
  chown -R niyam:niyam /data/var 2>/dev/null || true
  if command -v gosu >/dev/null 2>&1; then
    exec gosu niyam "$0" "$@"
  fi
fi
cmd="${1:-serve}"; shift || true
wait_db() {
  python - <<'PY'
import sys, time
from sqlalchemy import create_engine, text
from niyam.config import get_settings
e = create_engine(get_settings().database_url)
for i in range(60):
    try:
        with e.connect() as c: c.execute(text("select 1")); sys.exit(0)
    except Exception: time.sleep(1)
print("database not reachable", file=sys.stderr); sys.exit(1)
PY
}
# Preview-apply PDFs live in process memory. More than one worker makes those links fail at random.
port="${PORT:-8000}"
workers="${WEB_CONCURRENCY:-1}"
serve() {
  if [ "$workers" = "1" ]; then
    exec uvicorn niyam.main:app --host 0.0.0.0 --port "$port" --proxy-headers --forwarded-allow-ips='*' --no-server-header
  fi
  exec uvicorn niyam.main:app --host 0.0.0.0 --port "$port" --workers "$workers" --proxy-headers --forwarded-allow-ips='*' --no-server-header
}
case "$cmd" in
  serve)
    wait_db
    alembic upgrade head
    case "${NIYAM_INGEST_ON_START:-0}" in
      1|true|True|yes|YES) python -m niyam.kb.ingest & ;;
    esac
    serve
    ;;
  migrate) wait_db; exec alembic upgrade head ;;
  ingest)  wait_db; alembic upgrade head; exec python -m niyam.kb.ingest "$@" ;;
  eval)    wait_db; exec python -m niyam.kb.eval "$@" ;;
  test)    wait_db; alembic upgrade head; exec python -m pytest "$@" ;;
  *)       exec "$cmd" "$@" ;;
esac
