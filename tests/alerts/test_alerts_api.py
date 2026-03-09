"""Tests for Alert REST API endpoints."""

import pytest


# ── Helpers ──────────────────────────────────────────────────────────

ALERT_FORMULA = {
    "name": "RELIANCE above 1500",
    "symbol": "NSE:RELIANCE",
    "alert_type": "formula",
    "trigger_condition": {"formula": "C > 1500"},
    "frequency": "once",
}

ALERT_DRAWING = {
    "name": "Trendline cross",
    "symbol": "NSE:INFY",
    "alert_type": "drawing",
    "trigger_condition": {
        "drawing_type": "hline",
        "trigger_when": "crosses_above",
        "price": 1800.0,
    },
    "frequency": "once_per_minute",
    "drawing_id": "drawing_abc123",
}


async def _create_alert(client, token, body=None):
    """Helper to create an alert, returns response JSON."""
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/v1/alerts",
        json=body or ALERT_FORMULA,
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Create ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_formula_alert(client, token):
    data = await _create_alert(client, token)
    assert data["name"] == "RELIANCE above 1500"
    assert data["symbol"] == "NSE:RELIANCE"
    assert data["alert_type"] == "formula"
    assert data["status"] == "active"
    assert data["trigger_condition"]["formula"] == "C > 1500"
    assert data["frequency"] == "once"
    assert data["trigger_count"] == 0
    assert data["id"]


@pytest.mark.asyncio
async def test_create_drawing_alert(client, token):
    data = await _create_alert(client, token, ALERT_DRAWING)
    assert data["alert_type"] == "drawing"
    assert data["drawing_id"] == "drawing_abc123"
    assert data["trigger_condition"]["drawing_type"] == "hline"
    assert data["trigger_condition"]["price"] == 1800.0


@pytest.mark.asyncio
async def test_create_alert_with_guards(client, token):
    body = {
        **ALERT_FORMULA,
        "guard_conditions": [{"formula": "V > 100000"}, {"formula": "RSI(C,14) > 30"}],
    }
    data = await _create_alert(client, token, body)
    assert len(data["guard_conditions"]) == 2
    assert data["guard_conditions"][0]["formula"] == "V > 100000"


# ── List ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_alerts(client, token):
    headers = {"Authorization": f"Bearer {token}"}

    # Create two alerts
    await _create_alert(client, token)
    await _create_alert(client, token, {**ALERT_FORMULA, "name": "Second"})

    resp = await client.get("/api/v1/alerts", headers=headers)
    assert resp.status_code == 200
    alerts = resp.json()
    assert len(alerts) >= 2


@pytest.mark.asyncio
async def test_list_alerts_filter_by_symbol(client, token):
    headers = {"Authorization": f"Bearer {token}"}

    await _create_alert(client, token)
    await _create_alert(client, token, ALERT_DRAWING)

    resp = await client.get("/api/v1/alerts?symbol=NSE:INFY", headers=headers)
    assert resp.status_code == 200
    alerts = resp.json()
    assert all(a["symbol"] == "NSE:INFY" for a in alerts)


# ── Update ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_alert(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    data = await _create_alert(client, token)
    alert_id = data["id"]

    resp = await client.put(
        f"/api/v1/alerts/{alert_id}",
        json={
            "name": "Updated Name",
            "frequency": "once_per_bar",
            "trigger_condition": {"formula": "C > 2000"},
        },
        headers=headers,
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["name"] == "Updated Name"
    assert updated["frequency"] == "once_per_bar"
    assert updated["trigger_condition"]["formula"] == "C > 2000"


# ── Delete ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_alert(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    data = await _create_alert(client, token)
    alert_id = data["id"]

    resp = await client.delete(f"/api/v1/alerts/{alert_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    # Verify deletion
    resp = await client.get("/api/v1/alerts", headers=headers)
    ids = [a["id"] for a in resp.json()]
    assert alert_id not in ids


@pytest.mark.asyncio
async def test_delete_nonexistent_alert(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.delete("/api/v1/alerts/nonexistent-uuid", headers=headers)
    assert resp.status_code == 404


# ── Activate / Pause ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pause_and_activate_alert(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    data = await _create_alert(client, token)
    alert_id = data["id"]
    assert data["status"] == "active"

    # Pause
    resp = await client.post(f"/api/v1/alerts/{alert_id}/pause", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"

    # Activate
    resp = await client.post(f"/api/v1/alerts/{alert_id}/activate", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


@pytest.mark.asyncio
async def test_pause_already_paused(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    data = await _create_alert(client, token)
    alert_id = data["id"]

    await client.post(f"/api/v1/alerts/{alert_id}/pause", headers=headers)
    resp = await client.post(f"/api/v1/alerts/{alert_id}/pause", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"


# ── Drawing-linked delete ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_by_drawing(client, token):
    headers = {"Authorization": f"Bearer {token}"}

    # Create alert linked to a drawing
    await _create_alert(client, token, ALERT_DRAWING)

    resp = await client.delete(
        "/api/v1/alerts/by-drawing/drawing_abc123", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] >= 1


# ── Logs ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_logs_empty(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get("/api/v1/alerts/logs", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "logs" in data
    assert "total" in data
    assert data["total"] >= 0


@pytest.mark.asyncio
async def test_mark_logs_read(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    # Even with no logs, the endpoint should succeed
    resp = await client.post(
        "/api/v1/alerts/logs/read",
        json=[],
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["marked_read"] == 0


# ── Auth ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unauthorized_access(client):
    resp = await client.get("/api/v1/alerts")
    assert resp.status_code == 401

    resp = await client.get("/api/v1/alerts/logs")
    assert resp.status_code == 401

    resp = await client.post("/api/v1/alerts", json=ALERT_FORMULA)
    assert resp.status_code == 401
