import pytest
from unittest.mock import patch
from sqlalchemy import select, create_engine
from sqlalchemy.orm import Session, Mapped, mapped_column
from terminal.database import get_session, init_db
from terminal.models import Base


class Hero(Base):
    __tablename__ = "heroes"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]


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
        # 1. Initialize only the required table for this test
        Hero.__table__.create(test_engine)

        # 2. Get session and perform ops
        session_gen = get_session()
        session = next(session_gen)

        hero = Hero(name="Antigravity")
        session.add(hero)
        session.commit()
        session.refresh(hero)

        # 3. Query
        statement = select(Hero).where(Hero.name == "Antigravity")
        results = list(session.execute(statement).scalars().all())

        assert len(results) == 1
        assert results[0].name == "Antigravity"

        session.close()
