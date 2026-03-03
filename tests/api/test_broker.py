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
def broker_config(monkeypatch):
    monkeypatch.setattr(settings, "upstox_api_key", "test-key")
    monkeypatch.setattr(settings, "upstox_api_secret", "test-secret")
    monkeypatch.setattr(
        settings,
        "upstox_redirect_uri",
        "http://localhost:5173/broker/upstox/callback",
    )
    monkeypatch.setattr(settings, "kite_api_key", "")
    monkeypatch.setattr(settings, "kite_api_secret", "")
    monkeypatch.setattr(settings, "kite_redirect_uri", "")
    monkeypatch.setattr(settings, "encryption_key", Fernet.generate_key().decode())
    upstox = broker_registry.get("upstox")
    assert upstox is not None
    monkeypatch.setattr(upstox, "validate_token", AsyncMock(return_value=True))
    monkeypatch.setattr(upstox, "fetch_account_info", AsyncMock(return_value=None))


@pytest_asyncio.fixture
async def broker_token(client):
    username = f"broker_test_{uuid4().hex[:8]}"
    password = "testpassword"
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200
    return create_access_token({"sub": username})


@pytest.mark.asyncio
async def test_list_brokers_includes_upstox_when_configured(client, broker_token, broker_config):
    response = await client.get(
        "/api/v1/broker",
        headers={"Authorization": f"Bearer {broker_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["provider_id"] == "upstox"
    assert data[0]["login_required"] is True
    assert data[0]["connected"] is False
    assert data[0]["accounts"] == []


@pytest.mark.asyncio
async def test_broker_status_reflects_saved_token(client, broker_token, broker_config, monkeypatch):
    upstox = broker_registry.get("upstox")
    assert upstox is not None
    monkeypatch.setattr(upstox, "exchange_code", AsyncMock(return_value="access-token-1"))
    monkeypatch.setattr(
        upstox,
        "fetch_account_info",
        AsyncMock(
            return_value=BrokerAccountInfo(
                account_id="U12345",
                account_label="U12345",
                account_owner="Test Owner",
            )
        ),
    )

    callback_resp = await client.post(
        "/api/v1/broker/upstox/callback",
        json={"code": "abc"},
        headers={"Authorization": f"Bearer {broker_token}"},
    )
    assert callback_resp.status_code == 200

    status_resp = await client.get(
        "/api/v1/broker/upstox/status",
        headers={"Authorization": f"Bearer {broker_token}"},
    )
    assert status_resp.status_code == 200
    assert status_resp.json() == {
        "provider_id": "upstox",
        "connected": True,
        "login_required": False,
    }

    list_resp = await client.get(
        "/api/v1/broker",
        headers={"Authorization": f"Bearer {broker_token}"},
    )
    assert list_resp.status_code == 200
    assert list_resp.json()[0]["accounts"] == [
        {
            "account_key": "U12345",
            "credential_id": list_resp.json()[0]["accounts"][0]["credential_id"],
            "account_id": "U12345",
            "account_label": "U12345",
            "account_owner": "Test Owner",
        }
    ]


@pytest.mark.asyncio
async def test_set_and_list_defaults(client, broker_token, broker_config):
    set_resp = await client.put(
        "/api/v1/broker/defaults",
        json={
            "capability": "realtime_candles",
            "market": "india",
            "provider_id": "upstox",
        },
        headers={"Authorization": f"Bearer {broker_token}"},
    )
    assert set_resp.status_code == 200
    assert set_resp.json() == {
        "capability": "realtime_candles",
        "market": "india",
        "provider_id": "upstox",
    }

    list_resp = await client.get(
        "/api/v1/broker/defaults",
        headers={"Authorization": f"Bearer {broker_token}"},
    )
    assert list_resp.status_code == 200
    assert list_resp.json() == [
        {
            "capability": "realtime_candles",
            "market": "india",
            "provider_id": "upstox",
        }
    ]


@pytest.mark.asyncio
async def test_set_default_rejects_unsupported_market(client, broker_token, broker_config):
    response = await client.put(
        "/api/v1/broker/defaults",
        json={
            "capability": "realtime_candles",
            "market": "us",
            "provider_id": "upstox",
        },
        headers={"Authorization": f"Bearer {broker_token}"},
    )

    assert response.status_code == 400
    assert "does not support" in response.json()["detail"]


@pytest.mark.asyncio
async def test_broker_status_marks_invalid_token_as_login_required(
    client,
    broker_token,
    broker_config,
    monkeypatch,
):
    upstox = broker_registry.get("upstox")
    assert upstox is not None
    monkeypatch.setattr(upstox, "exchange_code", AsyncMock(return_value="access-token-2"))

    callback_resp = await client.post(
        "/api/v1/broker/upstox/callback",
        json={"code": "abc"},
        headers={"Authorization": f"Bearer {broker_token}"},
    )
    assert callback_resp.status_code == 200

    monkeypatch.setattr(upstox, "validate_token", AsyncMock(return_value=False))

    status_resp = await client.get(
        "/api/v1/broker/upstox/status",
        headers={"Authorization": f"Bearer {broker_token}"},
    )
    assert status_resp.status_code == 200
    assert status_resp.json() == {
        "provider_id": "upstox",
        "connected": False,
        "login_required": True,
    }

    list_resp = await client.get(
        "/api/v1/broker",
        headers={"Authorization": f"Bearer {broker_token}"},
    )
    assert list_resp.status_code == 200
    assert list_resp.json()[0]["connected"] is False
    assert list_resp.json()[0]["login_required"] is True


@pytest.mark.asyncio
async def test_broker_list_supports_multiple_accounts(
    client,
    broker_token,
    broker_config,
    monkeypatch,
):
    upstox = broker_registry.get("upstox")
    assert upstox is not None
    monkeypatch.setattr(upstox, "exchange_code", AsyncMock(return_value="access-token-3"))

    monkeypatch.setattr(
        upstox,
        "fetch_account_info",
        AsyncMock(
            side_effect=[
                BrokerAccountInfo(
                    account_id="A1",
                    account_label="Account A1",
                    account_owner="Owner One",
                ),
                BrokerAccountInfo(
                    account_id="A2",
                    account_label="Account A2",
                    account_owner="Owner Two",
                ),
            ]
        ),
    )

    for code in ("first", "second"):
        callback_resp = await client.post(
            "/api/v1/broker/upstox/callback",
            json={"code": code},
            headers={"Authorization": f"Bearer {broker_token}"},
        )
        assert callback_resp.status_code == 200

    list_resp = await client.get(
        "/api/v1/broker",
        headers={"Authorization": f"Bearer {broker_token}"},
    )
    assert list_resp.status_code == 200
    accounts = list_resp.json()[0]["accounts"]
    assert [a["account_id"] for a in accounts] == ["A2", "A1"]
    assert accounts[0]["account_owner"] == "Owner Two"
    assert accounts[1]["account_owner"] == "Owner One"


@pytest.mark.asyncio
async def test_broker_list_backfills_legacy_account_owner(
    client,
    broker_token,
    broker_config,
    monkeypatch,
):
    upstox = broker_registry.get("upstox")
    assert upstox is not None
    monkeypatch.setattr(upstox, "exchange_code", AsyncMock(return_value="legacy-token"))
    monkeypatch.setattr(upstox, "fetch_account_info", AsyncMock(return_value=None))

    callback_resp = await client.post(
        "/api/v1/broker/upstox/callback",
        json={"code": "legacy"},
        headers={"Authorization": f"Bearer {broker_token}"},
    )
    assert callback_resp.status_code == 200

    monkeypatch.setattr(
        upstox,
        "fetch_account_info",
        AsyncMock(
            return_value=BrokerAccountInfo(
                account_id="LEG1",
                account_label="Legacy Account",
                account_owner="Legacy Owner",
                raw_profile={"data": {"user_id": "LEG1", "user_name": "Legacy Owner"}},
            )
        ),
    )

    list_resp = await client.get(
        "/api/v1/broker",
        headers={"Authorization": f"Bearer {broker_token}"},
    )
    assert list_resp.status_code == 200
    account = list_resp.json()[0]["accounts"][0]
    assert account["account_label"] == "Legacy Account"
    assert account["account_owner"] == "Legacy Owner"


@pytest.mark.asyncio
async def test_delete_broker_account(
    client,
    broker_token,
    broker_config,
    monkeypatch,
):
    upstox = broker_registry.get("upstox")
    assert upstox is not None
    monkeypatch.setattr(upstox, "exchange_code", AsyncMock(return_value="access-token-4"))
    monkeypatch.setattr(
        upstox,
        "fetch_account_info",
        AsyncMock(
            side_effect=[
                BrokerAccountInfo(
                    account_id="DEL1",
                    account_label="Delete Me",
                    account_owner="Owner A",
                ),
                BrokerAccountInfo(
                    account_id="DEL2",
                    account_label="Keep Me",
                    account_owner="Owner B",
                ),
            ]
        ),
    )

    for code in ("one", "two"):
        callback_resp = await client.post(
            "/api/v1/broker/upstox/callback",
            json={"code": code},
            headers={"Authorization": f"Bearer {broker_token}"},
        )
        assert callback_resp.status_code == 200

    list_before = await client.get(
        "/api/v1/broker",
        headers={"Authorization": f"Bearer {broker_token}"},
    )
    assert list_before.status_code == 200
    accounts_before = list_before.json()[0]["accounts"]
    del1 = next(a for a in accounts_before if a["account_id"] == "DEL1")

    delete_resp = await client.delete(
        f"/api/v1/broker/upstox/accounts/{del1['credential_id']}",
        headers={"Authorization": f"Bearer {broker_token}"},
    )
    assert delete_resp.status_code == 200

    list_after = await client.get(
        "/api/v1/broker",
        headers={"Authorization": f"Bearer {broker_token}"},
    )
    assert list_after.status_code == 200
    accounts_after = list_after.json()[0]["accounts"]
    assert [a["account_id"] for a in accounts_after] == ["DEL2"]
