from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from niyam.api import check as check_api, fix as fix_api, guard as guard_api, kb as kb_api, review as review_api, rules as rules_api
from niyam.config import get_settings
from niyam.db.session import get_engine, tx

log = logging.getLogger("niyam")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    logging.basicConfig(level=s.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if s.env == "prod" and not s.api_key:
        raise RuntimeError("NIYAM_API_KEY must be set when NIYAM_ENV=prod (fail closed)")
    if s.sync_rules_on_start:
        from niyam.rules import loader
        try:
            with tx() as c:
                log.info("rule cards synced: %s", loader.sync(c))
            with tx() as c:
                from niyam.review import service
                log.info("rule approval items created: %s", service.ensure_rule_approvals(c))
        except Exception:  # noqa: BLE001
            log.exception("rule card sync failed; serving whatever is already in the database")
    yield
    get_engine().dispose()


app = FastAPI(title="Niyam API", version="0.1.0", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(HTTPException)
async def http_exc(_: Request, exc: HTTPException):
    d = exc.detail if isinstance(exc.detail, dict) else {"code": "http_error", "message": str(exc.detail)}
    body = {"code": d.get("code", "http_error"), "message": d.get("message", ""), **{k: v for k, v in d.items() if k not in ("code", "message")}}
    return JSONResponse(status_code=exc.status_code, content={"error": body})


@app.exception_handler(RequestValidationError)
async def validation_exc(_: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    return _err(422, "validation_error", f"{'.'.join(str(x) for x in first.get('loc', []))}: {first.get('msg', 'invalid request')}")


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.exception("unhandled error")
    return _err(500, "internal_error", "internal error")


@app.middleware("http")
async def access_log(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    t0 = time.perf_counter()
    resp = await call_next(request)
    resp.headers["x-request-id"] = rid
    resp.headers["x-content-type-options"] = "nosniff"
    resp.headers["cache-control"] = "no-store"
    if not request.url.path.startswith("/healthz"):
        log.info("%s %s %s %dms rid=%s", request.method, request.url.path, resp.status_code, (time.perf_counter() - t0) * 1000, rid)
    return resp


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict:
    return {"ok": True}


@app.get("/readyz", include_in_schema=False)
def readyz() -> dict:
    try:
        with tx() as c:
            c.execute(text("SELECT 1"))
            docs = c.execute(text("SELECT count(*) FROM documents")).scalar()
        return {"ok": True, "documents": docs}
    except Exception:  # noqa: BLE001
        return _err(503, "db_unavailable", "database not ready")


for r in (rules_api.router, kb_api.router, check_api.router, fix_api.router, guard_api.router, review_api.router):
    app.include_router(r, prefix="/api/v1")
