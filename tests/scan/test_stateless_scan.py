import pytest
from httpx import AsyncClient
import pandas as pd
from unittest.mock import AsyncMock


@pytest.fixture
def mock_market_manager():
    class MockManager:
        def get_ohlcv(self, symbol, timeframe="D"):
            # Return some dummy data
            df = pd.DataFrame(
                {
                    "open": [100, 110],
                    "high": [105, 115],
                    "low": [95, 105],
                    "close": [103, 112],
                    "volume": [1000, 1200],
                },
                index=[1000, 2000],
            )
            df.index.name = "timestamp"
            for col in ["open", "high", "low", "close", "volume"]:
                df[col[0].upper()] = df[col]
            return df

    return MockManager()


@pytest.mark.asyncio
async def test_run_stateless_scan(
    client: AsyncClient, token: str, mock_market_manager, monkeypatch
):
    headers = {"Authorization": f"Bearer {token}"}

    # Override dependencies
    from terminal.dependencies import get_market_manager, get_fs, get_settings
    from terminal.main import api
    from terminal.symbols import service as symbols_service

    api.dependency_overrides[get_market_manager] = lambda: mock_market_manager

    # Mock symbols service search to return AAPL
    async def mock_search(*args, **kwargs):
        return [{"ticker": "AAPL", "name": "Apple"}]

    monkeypatch.setattr(symbols_service, "search", mock_search)

    # Run stateless scan
    payload = {
        "name": "Test Stateless Scan",
        "source": None,  # None should trigger searching all (mocked to AAPL)
        "conditions": [
            {
                "formula": "C > O",
                "true_when": "now",
                "evaluation_type": "boolean",
                "type": "computed",
            }
        ],
        "conditional_logic": "and",
        "columns": [
            {"id": "Price", "name": "Price", "type": "value", "expression": "C"}
        ],
    }

    response = await client.post(
        "/api/v1/scans/run_stateless", headers=headers, json=payload
    )

    assert response.status_code == 200
    results = response.json()
    assert results["total"] == 1
    assert results["tickers"] == ["AAPL"]
    assert results["values"] == [[112.0]]

    # Clean up
    api.dependency_overrides.clear()
