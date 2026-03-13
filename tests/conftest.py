import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
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


@pytest_asyncio.fixture(name="session", scope="function")
async def session_fixture(postgres_container):
    """Provide an async SQLAlchemy session using the PostgreSQL container."""
    sync_url = postgres_container.get_connection_url().replace("+psycopg2", "+psycopg")
    async_url = sync_url.replace("+psycopg", "+psycopg_async")

    # Use sync engine only for table creation (init_db uses sqlalchemy_utils which is sync)
    sync_engine = create_engine(sync_url)
    init_db(sync_engine)
    sync_engine.dispose()

    # Use async engine for actual test operations
    test_engine = create_async_engine(async_url)
    TestAsyncSession = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    async with TestAsyncSession() as session:
        yield session
        await session.rollback()
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest_asyncio.fixture(name="client")
async def client_fixture(session):
    async def get_session_override():
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
