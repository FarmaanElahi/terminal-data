import pytest
from internal.database import DatabaseHandler
from sqlmodel import select, SQLModel, Field


class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


def test_database_lifecycle():
    """
    Tests the full database lifecycle using a direct DatabaseHandler instance.
    """
    db_url = "sqlite:///:memory:"
    handler = DatabaseHandler(database_url=db_url)

    # 1. Initialize DB
    handler.init_db()

    # 2. Get session and perform ops
    session_gen = handler.get_session()
    session = next(session_gen)

    hero = Hero(name="Antigravity")
    session.add(hero)
    session.commit()
    session.refresh(hero)

    # 3. Query
    statement = select(Hero).where(Hero.name == "Antigravity")
    results = session.exec(statement).all()

    assert len(results) == 1
    assert results[0].name == "Antigravity"

    session.close()
