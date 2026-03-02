from collections.abc import Generator
from sqlalchemy.orm import Session, DeclarativeBase
from sqlalchemy import create_engine
from terminal.config import settings
from terminal.enums import LogLevels
from terminal.database.logging import SessionTracker

engine = create_engine(
    settings.database_url,
    echo=(settings.log_level == LogLevels.debug),
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={"options": "-c statement_timeout=30000"},
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


def get_session() -> Generator[Session, None, None]:
    session = Session(engine)
    session_id = SessionTracker.track_session(session)
    try:
        yield session
        session.commit()

    except Exception as e:
        session.rollback()
        raise e

    finally:
        SessionTracker.untrack_session(session_id)
        session.close()
