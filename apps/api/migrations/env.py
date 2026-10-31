from alembic import context
from sqlalchemy import create_engine, pool

from niyam.config import get_settings

config = context.config


def run() -> None:
    url = get_settings().database_url
    if context.is_offline_mode():
        context.configure(url=url, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as conn:
        context.configure(connection=conn)
        with context.begin_transaction():
            context.run_migrations()


run()
