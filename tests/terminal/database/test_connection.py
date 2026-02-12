from sqlmodel import Session, text
from terminal.database.engine import engine


def test_database_connection():
    """
    Test that we can connect to the database and run a simple query.
    """
    with Session(engine) as session:
        result = session.scalar(text("SELECT 1 + 1"))
        assert result == 2
