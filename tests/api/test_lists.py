import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlmodel import Session, create_engine, SQLModel
from terminal.main import api
from terminal.database import get_session


@pytest.fixture(name="session")
def session_fixture():
    # Use SQLite for testing
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
async def test_create_and_get_list(client):
    # Create
    resp = await client.post(
        "/api/v1/list/", json={"name": "Test List", "type": "simple"}
    )
    assert resp.status_code == 200
    data = resp.json()
    list_id = data["id"]

    # Get
    resp = await client.get(f"/api/v1/list/{list_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test List"
    assert data["type"] == "simple"
    assert data["symbols"] == []


@pytest.mark.asyncio
async def test_append_and_remove_symbols(client):
    # Create
    resp = await client.post("/api/v1/list/", json={"name": "Simple", "type": "simple"})
    list_id = resp.json()["id"]

    # Append
    resp = await client.post(
        f"/api/v1/list/{list_id}/append", json={"symbols": ["AAPL", "MSFT"]}
    )
    assert resp.status_code == 200

    # Verify
    resp = await client.get(f"/api/v1/list/{list_id}")
    assert set(resp.json()["symbols"]) == {"AAPL", "MSFT"}

    # Bulk remove
    resp = await client.post(
        f"/api/v1/list/{list_id}/bulk_remove", json={"symbols": ["AAPL"]}
    )
    assert resp.status_code == 200

    # Verify
    resp = await client.get(f"/api/v1/list/{list_id}")
    assert resp.json()["symbols"] == ["MSFT"]
