"""Tests for the notifications REST API endpoints."""

import pytest


CHANNEL_TELEGRAM = {
    "channel_type": "telegram",
    "config": {"chat_id": "123456789"},
}

CHANNEL_WEB_PUSH = {
    "channel_type": "web_push",
    "config": {
        "subscription": {
            "endpoint": "https://fcm.googleapis.com/fcm/send/test",
            "keys": {"p256dh": "testkey", "auth": "testauthkey"},
        }
    },
}


@pytest.mark.asyncio
async def test_create_notification_channel(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/v1/notifications/channels",
        json=CHANNEL_TELEGRAM,
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["channel_type"] == "telegram"
    assert data["config"]["chat_id"] == "123456789"
    assert data["is_active"] is True
    assert data["id"]


@pytest.mark.asyncio
async def test_list_notification_channels(client, token):
    headers = {"Authorization": f"Bearer {token}"}

    # Create two channels
    await client.post(
        "/api/v1/notifications/channels", json=CHANNEL_TELEGRAM, headers=headers
    )
    await client.post(
        "/api/v1/notifications/channels", json=CHANNEL_WEB_PUSH, headers=headers
    )

    resp = await client.get("/api/v1/notifications/channels", headers=headers)
    assert resp.status_code == 200
    channels = resp.json()
    assert len(channels) >= 2
    types = {c["channel_type"] for c in channels}
    assert "telegram" in types
    assert "web_push" in types


@pytest.mark.asyncio
async def test_delete_notification_channel(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/v1/notifications/channels", json=CHANNEL_TELEGRAM, headers=headers
    )
    channel_id = resp.json()["id"]

    resp = await client.delete(
        f"/api/v1/notifications/channels/{channel_id}", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_get_vapid_public_key(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get("/api/v1/notifications/vapid-key", headers=headers)
    # 200 if VAPID key is configured, 503 if not — both are valid
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        data = resp.json()
        assert "public_key" in data
    else:
        assert resp.json()["detail"] == "Web Push not configured"


@pytest.mark.asyncio
async def test_unauthorized_notifications(client):
    resp = await client.get("/api/v1/notifications/channels")
    assert resp.status_code == 401

    resp = await client.post(
        "/api/v1/notifications/channels", json=CHANNEL_TELEGRAM
    )
    assert resp.status_code == 401
