# syntax=docker/dockerfile:1
# One image for Render: built web console + API + rule cards + demo library + cited regulations.
# Build from the repo root. Local compose still uses apps/api/Dockerfile (corpus via volumes).

FROM node:24-alpine AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM python:3.12-slim AS api
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends gosu \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 10001 --home /app niyam

COPY apps/api/pyproject.toml ./
RUN python - <<'PY' > /tmp/req.txt
import tomllib
print("\n".join(tomllib.load(open("pyproject.toml", "rb"))["project"]["dependencies"]))
PY
RUN pip install -r /tmp/req.txt

COPY apps/api/alembic.ini ./
COPY apps/api/migrations ./migrations
COPY apps/api/niyam ./niyam
COPY apps/api/docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

COPY --from=web /web/dist /app/console
COPY rules /data/rules
COPY library /data/library
COPY regulations /data/regulations
RUN mkdir -p /data/var/blobs /data/paytm-terms \
 && chown -R niyam:niyam /app /data

ENV PYTHONPATH=/app \
    NIYAM_DATA_ROOT=/data \
    NIYAM_CONSOLE_DIR=/app/console \
    NIYAM_BLOB_DIR=/data/var/blobs \
    WEB_CONCURRENCY=1

# Stay root so the entrypoint can chown the Render disk at /data/var, then drop to uid 10001.
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=40s --retries=5 \
  CMD python -c "import os,urllib.request,sys; p=os.environ.get('PORT','8000'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{p}/healthz', timeout=2).status==200 else 1)"
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["serve"]
