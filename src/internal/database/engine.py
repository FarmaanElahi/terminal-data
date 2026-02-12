from collections.abc import Generator
from sqlmodel import create_engine, Session, SQLModel
from sqlalchemy.engine import Engine


class DatabaseHandler:
    """
    Manages database engine and sessions without global state.
    """

    def __init__(self, database_url: str, echo: bool = True):
        self.database_url = database_url
        self.engine: Engine = create_engine(database_url, echo=echo)

    def get_session(self) -> Generator[Session, None, None]:
        with Session(self.engine) as session:
            yield session

    def init_db(self):
        SQLModel.metadata.create_all(self.engine)
