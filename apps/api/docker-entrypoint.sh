#!/bin/sh
set -eu
cmd="${1:-serve}"; shift || true
wait_db() {
  python - <<'PY'
import os, sys, time
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
case "$cmd" in
  serve)   wait_db; alembic upgrade head; exec uvicorn niyam.main:app --host 0.0.0.0 --port 8000 --workers "${WEB_CONCURRENCY:-2}" --proxy-headers --no-server-header ;;
  migrate) wait_db; exec alembic upgrade head ;;
  ingest)  wait_db; alembic upgrade head; exec python -m niyam.kb.ingest "$@" ;;
  eval)    wait_db; exec python -m niyam.kb.eval "$@" ;;
  test)    wait_db; alembic upgrade head; exec python -m pytest "$@" ;;
  *)       exec "$cmd" "$@" ;;
esac
