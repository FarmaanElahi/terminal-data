import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_column_set(client: AsyncClient, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    # Create a column set
    response = await client.post(
        "/api/v1/columns/",
        headers=headers,
        json={
            "name": "Default Columns",
            "columns": [
                {
                    "id": "col_macd",
                    "name": "MACD Value",
                    "type": "value",
                    "timeframe": "D",
                    "formula": "MACD",
                },
                {
                    "id": "col_rsi",
                    "name": "RSI",
                    "type": "value",
                    "formula": "RSI(14)",
                    "bar_ago": 1,
                },
            ],
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    cs_id = data["id"]
    assert data["name"] == "Default Columns"
    assert len(data["columns"]) == 2
    assert data["columns"][0]["id"] == "col_macd"
    assert data["columns"][0]["formula"] == "MACD"
    assert data["columns"][1]["bar_ago"] == 1

    # List all column sets
    response = await client.get("/api/v1/columns/", headers=headers)
    assert response.status_code == 200
    column_sets = response.json()
    assert len(column_sets) >= 1
    assert any(cs["id"] == cs_id for cs in column_sets)

    # Get by ID
    response = await client.get(f"/api/v1/columns/{cs_id}", headers=headers)
    assert response.status_code == 200
    cs = response.json()
    assert cs["name"] == "Default Columns"

    # Update
    response = await client.put(
        f"/api/v1/columns/{cs_id}",
        headers=headers,
        json={
            "name": "Updated Columns",
            "columns": [
                {
                    "id": "col_sma",
                    "name": "SMA 200",
                    "type": "value",
                    "formula": "SMA(C, 200)",
                },
            ],
        },
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "Updated Columns"
    assert len(updated["columns"]) == 1
    assert updated["columns"][0]["id"] == "col_sma"

    # Delete
    response = await client.delete(f"/api/v1/columns/{cs_id}", headers=headers)
    assert response.status_code == 200

    # Verify deleted
    response = await client.get(f"/api/v1/columns/{cs_id}", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_column_set_with_condition_on_column(client: AsyncClient, token: str):
    """Individual columns can reference a condition set via condition_id."""
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/v1/columns/",
        headers=headers,
        json={
            "name": "Filtered Columns",
            "columns": [
                {
                    "id": "c1",
                    "name": "Close",
                    "type": "value",
                    "formula": "C",
                    "condition_id": "some-condition-set-id",
                    "condition_logic": "and",
                    "filter": "active",
                },
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["columns"][0]["condition_id"] == "some-condition-set-id"
    assert data["columns"][0]["condition_logic"] == "and"
    assert data["columns"][0]["filter"] == "active"


@pytest.mark.asyncio
async def test_column_set_not_found(client: AsyncClient, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/columns/nonexistent-id", headers=headers)
    assert response.status_code == 404

    response = await client.put(
        "/api/v1/columns/nonexistent-id",
        headers=headers,
        json={"name": "x"},
    )
    assert response.status_code == 404

    response = await client.delete("/api/v1/columns/nonexistent-id", headers=headers)
    assert response.status_code == 404
