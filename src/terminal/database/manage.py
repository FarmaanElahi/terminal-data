from sqlalchemy import create_engine, text
from sqlalchemy_utils import database_exists, create_database, drop_database

from terminal.config import settings
from terminal.database.core import Base


def _make_sync_engine(engine_input=None):
    if engine_input:
        return engine_input
    return create_engine(settings.database_url)


def init_db(engine_input=None):
    use_engine = _make_sync_engine(engine_input)
    if not database_exists(use_engine.url):
        create_database(use_engine.url)

    with use_engine.begin() as conn:
        if use_engine.dialect.name == "postgresql":
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    # Import all models here to ensure they are registered in Base.metadata
    from terminal.auth.models import User  # noqa: F401
    from terminal.lists.models import List  # noqa: F401
    from terminal.preferences.models import UserPreferences  # noqa: F401

    Base.metadata.create_all(use_engine)


def drop_db():
    sync_engine = _make_sync_engine()
    if database_exists(sync_engine.url):
        drop_database(sync_engine.url)
