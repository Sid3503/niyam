from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

from niyam.config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_size=5, max_overflow=5, pool_pre_ping=True, future=True)
    return _engine


@contextmanager
def tx() -> Iterator[Connection]:
    """One transaction per unit of work; commits on success, rolls back on error."""
    with get_engine().begin() as conn:
        yield conn
