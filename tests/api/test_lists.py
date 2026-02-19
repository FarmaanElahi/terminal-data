import pytest


@pytest.mark.asyncio
async def test_create_and_get_list(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    # Create
    resp = await client.post(
        "/api/v1/lists/",
        json={"name": "Test List", "type": "simple"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    list_id = data["id"]

    # Get
    resp = await client.get(f"/api/v1/lists/{list_id}", headers=headers)
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
        "/api/v1/lists/",
        json={"name": "Simple", "type": "simple"},
        headers=headers,
    )
    list_id = resp.json()["id"]

    # Append
    resp = await client.post(
        f"/api/v1/lists/{list_id}/append_symbols",
        json={"symbols": ["AAPL", "MSFT"]},
        headers=headers,
    )
    assert resp.status_code == 200

    # Verify
    resp = await client.get(f"/api/v1/lists/{list_id}", headers=headers)
    assert set(resp.json()["symbols"]) == {"AAPL", "MSFT"}

    # Bulk remove
    resp = await client.post(
        f"/api/v1/lists/{list_id}/bulk_remove_symbols",
        json={"symbols": ["AAPL"]},
        headers=headers,
    )
    assert resp.status_code == 200

    # Verify
    resp = await client.get(f"/api/v1/lists/{list_id}", headers=headers)
    assert resp.json()["symbols"] == ["MSFT"]


@pytest.mark.asyncio
async def test_combo_source_list_management(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    # Create two simple lists
    l1 = await client.post(
        "/api/v1/lists/", json={"name": "L1", "type": "simple"}, headers=headers
    )
    l2 = await client.post(
        "/api/v1/lists/", json={"name": "L2", "type": "simple"}, headers=headers
    )
    l1_id, l2_id = l1.json()["id"], l2.json()["id"]

    # Create a combo list
    combo = await client.post(
        "/api/v1/lists/",
        json={"name": "Combo", "type": "combo", "source_list_ids": [l1_id]},
        headers=headers,
    )
    combo_id = combo.json()["id"]

    # Append source list
    resp = await client.post(
        f"/api/v1/lists/{combo_id}/append_source_lists",
        json={"source_list_ids": [l2_id]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert set(resp.json()["source_list_ids"]) == {l1_id, l2_id}

    # Bulk remove source list
    resp = await client.post(
        f"/api/v1/lists/{combo_id}/bulk_remove_source_lists",
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
        "/api/v1/lists/",
        json={"name": "Old Name", "type": "simple"},
        headers=headers,
    )
    list_id = resp.json()["id"]

    # Update name
    resp = await client.put(
        f"/api/v1/lists/{list_id}",
        json={"name": "New Name"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"

    # Verify get
    resp = await client.get(f"/api/v1/lists/{list_id}", headers=headers)
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_unauthorized_access(client):
    # Try to list without token
    resp = await client.get("/api/v1/lists/")
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
    resp = await client.get("/api/v1/lists/", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Verify 5 default color lists are created
    assert len(data) == 5
    colors = {lst["color"] for lst in data}
    assert colors == {"red", "green", "yellow", "blue", "purple"}
