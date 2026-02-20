import numpy as np
import pytest
from httpx import AsyncClient


# Provide mock OHLCV arrays to simulate MarketDataManager.get_ohlcv
# Daily mock data
def get_mock_ohlcv(symbol: str, timeframe: str = "D"):
    if symbol == "AAPL":
        return {
            "timestamp": np.array([1000, 2000, 3000, 4000]),
            "open": np.array([100, 105, 110, 108]),
            "high": np.array([105, 112, 115, 120]),
            "low": np.array([95, 100, 105, 105]),
            "close": np.array([103, 108, 112, 115]),
            "volume": np.array([1000, 1100, 1200, 1500]),
        }
    elif symbol == "MSFT":
        return {
            "timestamp": np.array([1000, 2000, 3000, 4000]),
            "open": np.array([200, 205, 210, 208]),
            "high": np.array([205, 212, 215, 210]),
            "low": np.array([195, 200, 205, 200]),
            "close": np.array([203, 208, 202, 205]),
            "volume": np.array([5000, 5100, 5200, 5500]),
        }
    return None


@pytest.fixture
def mock_market_manager(monkeypatch):
    class MockManager:
        def get_ohlcv(self, symbol, timeframe="D"):
            return get_mock_ohlcv(symbol, timeframe)

    # We patch the Dependency Injection inside the app
    # FastApi uses dependency overrides
    return MockManager()


@pytest.mark.asyncio
async def test_run_scan_engine(client: AsyncClient, token: str, mock_market_manager):
    headers = {"Authorization": f"Bearer {token}"}

    # Override the market manager dependency
    from terminal.dependencies import get_market_manager
    from terminal.main import api

    api.dependency_overrides[get_market_manager] = lambda: mock_market_manager

    # 1. Create a List to get a valid source ID
    list_response = await client.post(
        "/api/v1/lists/",
        headers=headers,
        json={"name": "Tech Stocks", "type": "simple"},
    )
    assert list_response.status_code == 200
    list_id = list_response.json()["id"]

    # Add symbols AAPL and MSFT to the list
    await client.post(
        f"/api/v1/lists/{list_id}/append_symbols",
        headers=headers,
        json={"symbols": ["AAPL", "MSFT"]},
    )

    # 2. Create the Scan
    scan_response = await client.post(
        "/api/v1/scans/",
        headers=headers,
        json={
            "name": "Up-trending Scan",
            "sources": list_id,
            "conditions": [
                {
                    # Condition: Close must be greater than Open
                    "formula": "C > O",
                    "true_when": "now",
                    "evaluation_type": "boolean",
                    "type": "computed",
                },
                {
                    # Condition: Close must be greater than 105
                    "formula": "C > 105",
                    "true_when": "within_last",
                    "true_when_param": 1,
                    "evaluation_type": "boolean",
                    "type": "computed",
                },
            ],
            "conditional_logic": "and",
            "columns": [
                {
                    "id": "CurrentClose",
                    "name": "Close Price",
                    "type": "value",
                    "timeframe": "D",
                    "expression": "C",
                },
                {
                    "id": "PreviousClose",
                    "name": "Previous Close",
                    "type": "value",
                    "timeframe": "D",
                    "expression": "C",
                    "bar_ago": 1,
                },
            ],
        },
    )
    assert scan_response.status_code == 200
    scan_id = scan_response.json()["id"]

    # 3. Run the scan
    run_response = await client.post(f"/api/v1/scans/{scan_id}/run", headers=headers)
    assert run_response.status_code == 200

    results = run_response.json()

    # Let's check our mock data:
    # AAPL: C = 115, O = 108. (C > O) is True. (C > 105) is True. Should pass.
    # MSFT: C = 205, O = 208. (C > O) is False. Should fail.

    assert len(results) == 1
    aapl_res = results[0]
    assert aapl_res["symbol"] == "AAPL"
    assert aapl_res["CurrentClose"] == 115
    assert aapl_res["PreviousClose"] == 112

    # Clean up overrides
    api.dependency_overrides.clear()
