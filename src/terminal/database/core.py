from collections.abc import Generator
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from terminal.config import settings
from terminal.database.logging import SessionTracker

engine = create_engine(settings.database_url, echo=True)


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
