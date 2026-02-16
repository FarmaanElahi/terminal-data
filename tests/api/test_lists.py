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


@pytest_asyncio.fixture(name="token")
async def token_fixture(client):
    # Register and login to get a token
    await client.post(
        "/api/v1/auth/register",
        json={"username": "listuser", "password": "listpassword"},
    )
    resp = await client.post(
        "/api/v1/auth/login", data={"username": "listuser", "password": "listpassword"}
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_create_and_get_list(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    # Create
    resp = await client.post(
        "/api/v1/list/",
        json={"name": "Test List", "type": "simple"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    list_id = data["id"]

    # Get
    resp = await client.get(f"/api/v1/list/{list_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test List"
    assert data["type"] == "simple"
    assert data["symbols"] == []


@pytest.mark.asyncio
async def test_append_and_remove_symbols(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    # Create
    resp = await client.post(
        "/api/v1/list/",
        json={"name": "Simple", "type": "simple"},
        headers=headers,
    )
    list_id = resp.json()["id"]

    # Append
    resp = await client.post(
        f"/api/v1/list/{list_id}/append_symbols",
        json={"symbols": ["AAPL", "MSFT"]},
        headers=headers,
    )
    assert resp.status_code == 200

    # Verify
    resp = await client.get(f"/api/v1/list/{list_id}", headers=headers)
    assert set(resp.json()["symbols"]) == {"AAPL", "MSFT"}

    # Bulk remove
    resp = await client.post(
        f"/api/v1/list/{list_id}/bulk_remove_symbols",
        json={"symbols": ["AAPL"]},
        headers=headers,
    )
    assert resp.status_code == 200

    # Verify
    resp = await client.get(f"/api/v1/list/{list_id}", headers=headers)
    assert resp.json()["symbols"] == ["MSFT"]


@pytest.mark.asyncio
async def test_combo_source_list_management(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    # Create two simple lists
    l1 = await client.post(
        "/api/v1/list/", json={"name": "L1", "type": "simple"}, headers=headers
    )
    l2 = await client.post(
        "/api/v1/list/", json={"name": "L2", "type": "simple"}, headers=headers
    )
    l1_id, l2_id = l1.json()["id"], l2.json()["id"]

    # Create a combo list
    combo = await client.post(
        "/api/v1/list/",
        json={"name": "Combo", "type": "combo", "source_list_ids": [l1_id]},
        headers=headers,
    )
    combo_id = combo.json()["id"]

    # Append source list
    resp = await client.post(
        f"/api/v1/list/{combo_id}/append_source_lists",
        json={"source_list_ids": [l2_id]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert set(resp.json()["source_list_ids"]) == {l1_id, l2_id}

    # Bulk remove source list
    resp = await client.post(
        f"/api/v1/list/{combo_id}/bulk_remove_source_lists",
        json={"source_list_ids": [l1_id]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["source_list_ids"] == [l2_id]


@pytest.mark.asyncio
async def test_update_list(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    # Create
    resp = await client.post(
        "/api/v1/list/",
        json={"name": "Old Name", "type": "simple"},
        headers=headers,
    )
    list_id = resp.json()["id"]

    # Update name
    resp = await client.put(
        f"/api/v1/list/{list_id}",
        json={"name": "New Name"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"

    # Verify get
    resp = await client.get(f"/api/v1/list/{list_id}", headers=headers)
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_unauthorized_access(client):
    # Try to list without token
    resp = await client.get("/api/v1/list/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_default_lists_initialization(client):
    # Register/Login a fresh user
    await client.post(
        "/api/v1/auth/register",
        json={"username": "newuser", "password": "newpassword"},
    )
    resp = await client.post(
        "/api/v1/auth/login", data={"username": "newuser", "password": "newpassword"}
    )
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Access lists for the first time
    resp = await client.get("/api/v1/list/", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Verify 5 default color lists are created
    assert len(data) == 5
    colors = {lst["color"] for lst in data}
    assert colors == {"red", "green", "yellow", "blue", "purple"}
