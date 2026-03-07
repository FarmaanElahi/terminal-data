import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from terminal.database.core import Base
from terminal.main import api
from terminal.dependencies import get_session
from terminal.database.manage import init_db
from dotenv import load_dotenv
from testcontainers.postgres import PostgresContainer

# Load .env file at the start of testing
load_dotenv()


@pytest.fixture(scope="session")
def postgres_container():
    """Start a PostgreSQL container for the entire test session."""
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres


@pytest.fixture(name="session")
def session_fixture(postgres_container):
    """Provide a SQLAlchemy session using the PostgreSQL container."""
    # Use psycopg (v3) dialect
    url = postgres_container.get_connection_url().replace("+psycopg2", "+psycopg")
    engine = create_engine(url)

    # Use init_db to ensure all models are registered and tables created
    init_db(engine)

    with Session(engine) as session:
        yield session
        # Cleanup: Drop all tables to ensure test isolation
        session.rollback()  # Ensure no pending transaction
        Base.metadata.drop_all(engine)


@pytest_asyncio.fixture(name="client")
async def client_fixture(session):
    def get_session_override():
        yield session

    # Clear auth rate limiter between tests to avoid 429s
    from terminal.auth.router import _LOGIN_ATTEMPTS
    _LOGIN_ATTEMPTS.clear()

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
