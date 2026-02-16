import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlmodel import Session, create_engine, SQLModel
from terminal.main import api
from terminal.database import get_session


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest_asyncio.fixture(name="client")
async def client_fixture(session):
    def get_session_override():
        yield session

    api.dependency_overrides[get_session] = get_session_override
    transport = ASGITransport(app=api)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    api.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_register_and_login(client):
    # Register
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "testuser", "password": "testpassword"},
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "testuser"

    # Login
    resp = await client.post(
        "/api/v1/auth/login", data={"username": "testuser", "password": "testpassword"}
    )
    assert resp.status_code == 200
    token_data = resp.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    # Protected route /me
    token = token_data["access_token"]
    resp = await client.get(
        "/api/v1/user/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "testuser"
