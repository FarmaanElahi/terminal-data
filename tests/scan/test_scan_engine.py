import pytest
from httpx import AsyncClient


import pandas as pd


# Provide mock OHLCV arrays to simulate MarketDataManager.get_ohlcv
# Daily mock data
def get_mock_ohlcv(symbol: str, timeframe: str = "D"):
    if symbol == "AAPL":
        df = pd.DataFrame(
            {
                "open": [100, 105, 110, 108],
                "high": [105, 112, 115, 120],
                "low": [95, 100, 105, 105],
                "close": [103, 108, 112, 115],
                "volume": [1000, 1100, 1200, 1500],
            },
            index=[1000, 2000, 3000, 4000],
        )
        df.index.name = "timestamp"
    elif symbol == "MSFT":
        df = pd.DataFrame(
            {
                "open": [200, 205, 210, 208],
                "high": [205, 212, 215, 210],
                "low": [195, 200, 205, 200],
                "close": [203, 208, 202, 205],
                "volume": [5000, 5100, 5200, 5500],
            },
            index=[1000, 2000, 3000, 4000],
        )
        df.index.name = "timestamp"
    else:
        return None

    # Add aliases
    df["O"] = df["open"]
    df["H"] = df["high"]
    df["L"] = df["low"]
    df["C"] = df["close"]
    df["V"] = df["volume"]
    return df


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
            "source": list_id,
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
    assert "columns" in results
    assert "values" in results
    assert results["columns"] == ["CurrentClose", "PreviousClose"]
    assert len(results["values"]) == 1

    aapl_row_dict = results["values"][0]
    assert aapl_row_dict["n"] == "AAPL"
    assert aapl_row_dict["v"] == [115, 112]

    # Clean up overrides
    api.dependency_overrides.clear()
