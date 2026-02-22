import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_condition_set(client: AsyncClient, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    # Create a condition set
    response = await client.post(
        "/api/v1/conditions/",
        headers=headers,
        json={
            "name": "Bullish Momentum",
            "conditions": [
                {"formula": "MACD > 0", "timeframe": "D"},
                {"formula": "RSI(14) > 50", "timeframe": "D"},
            ],
            "conditional_logic": "and",
            "timeframe": "fixed",
            "timeframe_value": "D",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    cs_id = data["id"]
    assert data["name"] == "Bullish Momentum"
    assert len(data["conditions"]) == 2
    assert data["conditions"][0]["formula"] == "MACD > 0"
    assert data["conditional_logic"] == "and"
    assert data["timeframe"] == "fixed"
    assert data["timeframe_value"] == "D"

    # List all condition sets
    response = await client.get("/api/v1/conditions/", headers=headers)
    assert response.status_code == 200
    condition_sets = response.json()
    assert len(condition_sets) >= 1
    assert any(cs["id"] == cs_id for cs in condition_sets)

    # Get by ID
    response = await client.get(f"/api/v1/conditions/{cs_id}", headers=headers)
    assert response.status_code == 200
    cs = response.json()
    assert cs["name"] == "Bullish Momentum"
    assert cs["timeframe"] == "fixed"

    # Update
    response = await client.put(
        f"/api/v1/conditions/{cs_id}",
        headers=headers,
        json={
            "name": "Bear Filter",
            "conditions": [
                {"formula": "MACD < 0", "timeframe": "D"},
            ],
            "conditional_logic": "or",
            "timeframe": "mixed",
        },
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "Bear Filter"
    assert len(updated["conditions"]) == 1
    assert updated["conditional_logic"] == "or"
    assert updated["timeframe"] == "mixed"
    assert updated["timeframe_value"] == "D"  # retained from create

    # Delete
    response = await client.delete(f"/api/v1/conditions/{cs_id}", headers=headers)
    assert response.status_code == 200

    # Verify deleted
    response = await client.get(f"/api/v1/conditions/{cs_id}", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_condition_set_mixed_timeframes(client: AsyncClient, token: str):
    """Conditions with mixed timeframes assign per-condition timeframes."""
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/v1/conditions/",
        headers=headers,
        json={
            "name": "Multi-TF Filter",
            "conditions": [
                {"formula": "C > SMA(C, 200)", "timeframe": "D"},
                {"formula": "C > SMA(C, 50)", "timeframe": "W"},
            ],
            "conditional_logic": "and",
            "timeframe": "mixed",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["timeframe"] == "mixed"
    assert data["conditions"][0]["timeframe"] == "D"
    assert data["conditions"][1]["timeframe"] == "W"


@pytest.mark.asyncio
async def test_condition_set_not_found(client: AsyncClient, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/conditions/nonexistent-id", headers=headers)
    assert response.status_code == 404

    response = await client.put(
        "/api/v1/conditions/nonexistent-id",
        headers=headers,
        json={"name": "x"},
    )
    assert response.status_code == 404

    response = await client.delete("/api/v1/conditions/nonexistent-id", headers=headers)
    assert response.status_code == 404
