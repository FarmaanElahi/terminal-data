import pytest


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
