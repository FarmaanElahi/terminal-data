from sqlalchemy import text
from sqlalchemy_utils import database_exists, create_database, drop_database
from .core import engine

# Import all models here to ensure they are registered in Base.metadata
from terminal.models import Base
from terminal.auth.models import User
from terminal.lists.models import List
from terminal.symbols.models import Symbol


def init_db(engine_input=None):
    use_engine = engine_input or engine
    if not database_exists(use_engine.url):
        create_database(use_engine.url)

    with use_engine.begin() as conn:
        if use_engine.dialect.name == "postgresql":
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    Base.metadata.create_all(use_engine)


def drop_db():
    if database_exists(engine.url):
        drop_database(engine.url)
