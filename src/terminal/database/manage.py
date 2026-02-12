from sqlmodel import SQLModel
from sqlalchemy_utils import database_exists, create_database, drop_database
from .core import engine


def init_db():
    if not database_exists(engine.url):
        create_database(engine.url)
    SQLModel.metadata.create_all(engine)


def drop_db():
    if database_exists(engine.url):
        drop_database(engine.url)
