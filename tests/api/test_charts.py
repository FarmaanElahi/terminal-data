import pytest


SAMPLE_CONTENT = {"version": 1, "charts": [{"panes": []}]}


# ─── Chart CRUD ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_and_list_charts(client, token):
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/charts",
        json={
            "name": "My Chart",
            "symbol": "NSE:RELIANCE",
            "resolution": "1D",
            "content": SAMPLE_CONTENT,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "My Chart"
    assert data["symbol"] == "NSE:RELIANCE"
    assert data["resolution"] == "1D"
    chart_id = data["id"]

    # List
    resp = await client.get("/api/v1/charts", headers=headers)
    assert resp.status_code == 200
    charts = resp.json()
    assert any(c["id"] == chart_id for c in charts)


@pytest.mark.asyncio
async def test_get_chart_content(client, token):
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/charts",
        json={"name": "Content Test", "content": SAMPLE_CONTENT},
        headers=headers,
    )
    chart_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/charts/{chart_id}/content", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == chart_id
    assert data["content"] == SAMPLE_CONTENT


@pytest.mark.asyncio
async def test_update_chart(client, token):
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/charts",
        json={"name": "Old Name", "content": SAMPLE_CONTENT},
        headers=headers,
    )
    chart_id = resp.json()["id"]

    updated_content = {"version": 2, "charts": []}
    resp = await client.put(
        f"/api/v1/charts/{chart_id}",
        json={"name": "New Name", "content": updated_content},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"

    # Verify content updated
    resp = await client.get(f"/api/v1/charts/{chart_id}/content", headers=headers)
    assert resp.json()["content"] == updated_content


@pytest.mark.asyncio
async def test_delete_chart(client, token):
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/charts",
        json={"name": "To Delete", "content": SAMPLE_CONTENT},
        headers=headers,
    )
    chart_id = resp.json()["id"]

    resp = await client.delete(f"/api/v1/charts/{chart_id}", headers=headers)
    assert resp.status_code == 204

    # Should return 404 now
    resp = await client.get(f"/api/v1/charts/{chart_id}/content", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_chart_not_found(client, token):
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/v1/charts/nonexistent-id/content", headers=headers)
    assert resp.status_code == 404

    resp = await client.put(
        "/api/v1/charts/nonexistent-id",
        json={"name": "X"},
        headers=headers,
    )
    assert resp.status_code == 404

    resp = await client.delete("/api/v1/charts/nonexistent-id", headers=headers)
    assert resp.status_code == 404


# ─── Study Templates ──────────────────────────────────────────────────────────


SAMPLE_TEMPLATE_CONTENT = {"indicators": [{"name": "RSI", "inputs": {"length": 14}}]}


@pytest.mark.asyncio
async def test_create_and_list_study_templates(client, token):
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/charts/study-templates",
        json={"name": "RSI Setup", "content": SAMPLE_TEMPLATE_CONTENT},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "RSI Setup"

    resp = await client.get("/api/v1/charts/study-templates", headers=headers)
    assert resp.status_code == 200
    names = [t["name"] for t in resp.json()]
    assert "RSI Setup" in names


@pytest.mark.asyncio
async def test_get_study_template_content(client, token):
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        "/api/v1/charts/study-templates",
        json={"name": "MACD", "content": SAMPLE_TEMPLATE_CONTENT},
        headers=headers,
    )

    resp = await client.get(
        "/api/v1/charts/study-templates/MACD/content", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "MACD"
    assert resp.json()["content"] == SAMPLE_TEMPLATE_CONTENT


@pytest.mark.asyncio
async def test_upsert_study_template(client, token):
    headers = {"Authorization": f"Bearer {token}"}

    # Create
    await client.post(
        "/api/v1/charts/study-templates",
        json={"name": "EMA", "content": {"indicators": []}},
        headers=headers,
    )

    # Upsert (update)
    updated = {"indicators": [{"name": "EMA", "inputs": {"length": 20}}]}
    resp = await client.post(
        "/api/v1/charts/study-templates",
        json={"name": "EMA", "content": updated},
        headers=headers,
    )
    assert resp.status_code == 200

    # Verify updated content
    resp = await client.get(
        "/api/v1/charts/study-templates/EMA/content", headers=headers
    )
    assert resp.json()["content"] == updated


@pytest.mark.asyncio
async def test_delete_study_template(client, token):
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        "/api/v1/charts/study-templates",
        json={"name": "ToDelete", "content": {}},
        headers=headers,
    )

    resp = await client.delete(
        "/api/v1/charts/study-templates/ToDelete", headers=headers
    )
    assert resp.status_code == 204

    resp = await client.get(
        "/api/v1/charts/study-templates/ToDelete/content", headers=headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_study_template_not_found(client, token):
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(
        "/api/v1/charts/study-templates/nonexistent/content", headers=headers
    )
    assert resp.status_code == 404

    resp = await client.delete(
        "/api/v1/charts/study-templates/nonexistent", headers=headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_charts_unauthorized(client):
    resp = await client.get("/api/v1/charts")
    assert resp.status_code == 401
