from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet

from terminal.auth.security import create_access_token
from terminal.broker.adapter import BrokerAccountInfo
from terminal.broker.registry import broker_registry
from terminal.config import settings


@pytest.fixture
def kite_config(monkeypatch):
    monkeypatch.setattr(settings, "upstox_api_key", "")
    monkeypatch.setattr(settings, "upstox_api_secret", "")
    monkeypatch.setattr(settings, "upstox_redirect_uri", "")

    monkeypatch.setattr(settings, "kite_api_key", "kite-key")
    monkeypatch.setattr(settings, "kite_api_secret", "kite-secret")
    monkeypatch.setattr(
        settings,
        "kite_redirect_uri",
        "http://localhost:5173/broker/kite/callback",
    )
    monkeypatch.setattr(settings, "encryption_key", Fernet.generate_key().decode())

    kite = broker_registry.get("kite")
    assert kite is not None
    monkeypatch.setattr(kite, "validate_token", AsyncMock(return_value=True))
    monkeypatch.setattr(kite, "fetch_account_info", AsyncMock(return_value=None))


@pytest_asyncio.fixture
async def kite_token(client):
    username = f"kite_test_{uuid4().hex[:8]}"
    password = "testpassword"
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200
    return create_access_token({"sub": username})


@pytest.mark.asyncio
async def test_list_brokers_includes_kite_when_configured(client, kite_token, kite_config):
    response = await client.get(
        "/api/v1/broker",
        headers={"Authorization": f"Bearer {kite_token}"},
    )
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["provider_id"] == "kite"
    assert data[0]["display_name"] == "Zerodha Kite"
    assert data[0]["markets"] == ["india"]
    assert set(data[0]["capabilities"]) == {
        "alerts",
        "order_management",
        "positions",
        "holdings",
    }


@pytest.mark.asyncio
async def test_kite_connect_flow_saves_account_profile(
    client,
    kite_token,
    kite_config,
    monkeypatch,
):
    kite = broker_registry.get("kite")
    assert kite is not None
    monkeypatch.setattr(kite, "exchange_code", AsyncMock(return_value="kite-access-token"))
    monkeypatch.setattr(
        kite,
        "fetch_account_info",
        AsyncMock(
            return_value=BrokerAccountInfo(
                account_id="KITE123",
                account_label="kite-user",
                account_owner="Kite Owner",
                raw_profile={"data": {"user_id": "KITE123", "user_name": "Kite Owner"}},
            )
        ),
    )

    callback_resp = await client.post(
        "/api/v1/broker/kite/callback",
        json={"code": "request-token-from-kite"},
        headers={"Authorization": f"Bearer {kite_token}"},
    )
    assert callback_resp.status_code == 200

    list_resp = await client.get(
        "/api/v1/broker",
        headers={"Authorization": f"Bearer {kite_token}"},
    )
    assert list_resp.status_code == 200

    broker = list_resp.json()[0]
    assert broker["provider_id"] == "kite"
    assert broker["connected"] is True
    assert broker["login_required"] is False
    assert broker["accounts"][0]["account_id"] == "KITE123"
    assert broker["accounts"][0]["account_label"] == "kite-user"
    assert broker["accounts"][0]["account_owner"] == "Kite Owner"
