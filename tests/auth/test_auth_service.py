import pytest
from sqlmodel import Session, create_engine, SQLModel
from terminal.auth import service as auth_service
from terminal.auth.models import UserCreate


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_register_user(session: Session):
    user_in = UserCreate(username="testuser", password="testpassword")
    user = auth_service.create(session, user_in)
    assert user.id is not None
    assert user.username == "testuser"
    assert user.verify_password("testpassword")


def test_authenticate_user_success(session: Session):
    user_in = UserCreate(username="testuser", password="testpassword")
    auth_service.create(session, user_in)
    user = auth_service.authenticate(session, "testuser", "testpassword")
    assert user.username == "testuser"


def test_authenticate_user_failure(session: Session):
    user_in = UserCreate(username="testuser", password="testpassword")
    auth_service.create(session, user_in)

    user = auth_service.authenticate(session, "testuser", "wrongpassword")
    assert user is None
