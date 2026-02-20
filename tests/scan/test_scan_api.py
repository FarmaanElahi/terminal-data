import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_scan(client: AsyncClient, token: str):
    headers = {"Authorization": f"Bearer {token}"}

    # First create a List to get a valid source ID
    list_response = await client.post(
        "/api/v1/lists/",
        headers=headers,
        json={"name": "My Scan Source List", "type": "simple"},
    )
    assert list_response.status_code == 200, list_response.text
    list_id = list_response.json()["id"]

    # Provide auth headers for create
    response = await client.post(
        "/api/v1/scans/",
        headers=headers,
        json={
            "name": "My First Scan",
            "sources": list_id,
            "conditions": [
                {
                    "formula": "MACD > 0",
                    "true_when": "now",
                    "evaluation_type": "boolean",
                    "type": "computed",
                }
            ],
            "conditional_logic": "and",
            "columns": [
                {
                    "id": "col1",
                    "name": "MACD Value",
                    "type": "value",
                    "expression": "MACD",
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    scan_id = response.json()["id"]

    # Retrieve all scans
    response = await client.get("/api/v1/scans/", headers=headers)
    assert response.status_code == 200
    scans = response.json()
    assert len(scans) >= 1
    assert any(s["id"] == scan_id for s in scans)

    # Retrieve specific scan
    response = await client.get(f"/api/v1/scans/{scan_id}", headers=headers)
    assert response.status_code == 200
    scan = response.json()
    assert scan["name"] == "My First Scan"
    assert scan["sources"] == list_id
    assert len(scan["conditions"]) == 1
    assert scan["conditions"][0]["formula"] == "MACD > 0"
    assert len(scan["columns"]) == 1
    assert scan["columns"][0]["id"] == "col1"

    # Update scan
    response = await client.put(
        f"/api/v1/scans/{scan_id}",
        headers=headers,
        json={
            "name": "Updated Scan Name",
            "columns": [],
        },
    )
    assert response.status_code == 200
    updated_scan = response.json()
    assert updated_scan["name"] == "Updated Scan Name"
    assert len(updated_scan["columns"]) == 0

    # Delete scan
    response = await client.delete(f"/api/v1/scans/{scan_id}", headers=headers)
    assert response.status_code == 200

    # Verify deleted
    response = await client.get(f"/api/v1/scans/{scan_id}", headers=headers)
    assert response.status_code == 404
