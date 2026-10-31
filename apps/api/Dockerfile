FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# 1) dependency layer: cached until pyproject.toml changes
COPY pyproject.toml ./
ARG INSTALL_DEV=0
RUN INSTALL_DEV=${INSTALL_DEV} python - <<'PY' > /tmp/req.txt
import os, tomllib
p = tomllib.load(open("pyproject.toml", "rb"))["project"]
reqs = list(p["dependencies"]) + (p.get("optional-dependencies", {}).get("dev", []) if os.environ["INSTALL_DEV"] == "1" else [])
print("\n".join(reqs))
PY
RUN pip install -r /tmp/req.txt

# 2) application code
COPY alembic.ini ./
COPY migrations ./migrations
COPY niyam ./niyam
COPY tests ./tests
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh \
 && useradd --system --uid 10001 --home /app niyam && chown -R niyam /app
USER niyam
ENV PYTHONPATH=/app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status==200 else 1)"
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["serve"]
