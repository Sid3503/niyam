import os

import pytest
from sqlalchemy import text


def _db_up() -> bool:
    try:
        from niyam.db.session import get_engine
        with get_engine().connect() as c:
            c.execute(text("select 1"))
        return True
    except Exception:  # noqa: BLE001
        return False


def pytest_collection_modifyitems(config, items):
    if _db_up():
        return
    skip = pytest.mark.skip(reason="no Postgres reachable (set NIYAM_DATABASE_URL or use `make test`)")
    for it in items:
        if "db" in it.keywords:
            it.add_marker(skip)
