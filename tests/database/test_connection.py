import pytest
from unittest.mock import patch
from sqlmodel import select, SQLModel, Field, create_engine
from terminal.database import get_session, init_db


class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


def test_database_lifecycle():
    """
    Tests the full database lifecycle using global functions.
    """
    # Create fresh in-memory engine
    test_engine = create_engine("sqlite:///:memory:")

    # Patch the engine in both modules where it is used
    with (
        patch("terminal.database.core.engine", test_engine),
        patch("terminal.database.manage.engine", test_engine),
    ):
        # 1. Initialize DB (creates tables in memory)
        init_db()

        # 2. Get session and perform ops
        session_gen = get_session()
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
