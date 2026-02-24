import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_column_set(client: AsyncClient, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    # Create a column set with value columns
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
                    "value_type": "formula",
                    "value_formula": "MACD",
                    "value_formula_tf": "D",
                },
                {
                    "id": "col_rsi",
                    "name": "RSI",
                    "type": "value",
                    "value_type": "formula",
                    "value_formula": "RSI(14)",
                    "value_formula_x_bar_ago": 1,
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
    assert data["columns"][0]["value_formula"] == "MACD"
    assert data["columns"][1]["value_formula_x_bar_ago"] == 1

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
                    "value_type": "formula",
                    "value_formula": "SMA(C, 200)",
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
async def test_column_set_with_condition_column(client: AsyncClient, token: str):
    """Condition columns have inline conditions with filter state."""
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
                    "value_type": "formula",
                    "value_formula": "C",
                },
                {
                    "id": "c2",
                    "name": "Gap Up",
                    "type": "condition",
                    "filter": "active",
                    "conditions": [
                        {"formula": "C > C.1", "evaluate_as": "true"},
                    ],
                    "conditions_logic": "and",
                    "conditions_tf": "D",
                },
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["columns"][0]["type"] == "value"
    assert data["columns"][0]["value_formula"] == "C"
    assert data["columns"][1]["type"] == "condition"
    assert data["columns"][1]["filter"] == "active"
    assert len(data["columns"][1]["conditions"]) == 1
    assert data["columns"][1]["conditions"][0]["formula"] == "C > C.1"
    assert data["columns"][1]["conditions_logic"] == "and"


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
