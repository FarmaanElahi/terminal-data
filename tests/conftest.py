import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlmodel import Session, create_engine, SQLModel
from terminal.main import api
from terminal.database import get_session
from dotenv import load_dotenv

# Load .env file at the start of testing
load_dotenv()


@pytest.fixture(name="session")
def session_fixture():
    # Use SQLite for testing
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest_asyncio.fixture(name="client")
async def client_fixture(session):
    def get_session_override():
        yield session

    api.dependency_overrides[get_session] = get_session_override
    async with AsyncClient(
        transport=ASGITransport(app=api), base_url="http://testserver"
    ) as ac:
        yield ac
    api.dependency_overrides.clear()


@pytest_asyncio.fixture(name="token")
async def token_fixture(client):
    # Create a test user and get a token
    await client.post(
        "/api/v1/auth/register",
        json={"username": "testuser", "password": "testpassword"},
    )
    resp = await client.post(
        "/api/v1/auth/login", data={"username": "testuser", "password": "testpassword"}
    )
    return resp.json()["access_token"]
