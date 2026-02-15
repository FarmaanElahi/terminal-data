import pytest
import numpy as np
from fastapi.testclient import TestClient
from terminal.main import api
from unittest.mock import patch

client = TestClient(api)


@pytest.fixture
def mock_ohlc_data():
    return {
        "timestamp": np.array([1672531200], dtype=np.int64),
        "open": np.array([100.0], dtype=np.float64),
        "high": np.array([110.0], dtype=np.float64),
        "low": np.array([90.0], dtype=np.float64),
        "close": np.array([105.0], dtype=np.float64),
        "volume": np.array([5000.0], dtype=np.float64),
    }


def test_get_ohlcv_success(mock_ohlc_data):
    with patch("terminal.market_data.manager.MarketDataManager.get_ohlcv") as mock_get:
        mock_get.return_value = mock_ohlc_data

        response = client.get("/market-data/NSE:RELIANCE")

        assert response.status_code == 200
        data = response.json()
        assert data["close"] == [105.0]
        assert data["timestamp"] == [1672531200]


def test_get_ohlcv_not_found():
    with patch("terminal.market_data.manager.MarketDataManager.get_ohlcv") as mock_get:
        # First call returns None, then manager.load_history is called, then second get_ohlcv returns None
        mock_get.return_value = None

        with patch(
            "terminal.market_data.manager.MarketDataManager.load_history"
        ) as mock_load:
            mock_load.return_value = None

            response = client.get("/market-data/UNKNOWN")

            assert response.status_code == 404
            assert "No data found" in response.json()["detail"]


def test_get_ohlcv_refresh():
    with patch(
        "terminal.market_data.manager.MarketDataManager.load_history"
    ) as mock_load:
        with patch(
            "terminal.market_data.manager.MarketDataManager.get_ohlcv"
        ) as mock_get:
            mock_get.return_value = {
                "timestamp": [1],
                "open": [1],
                "high": [1],
                "low": [1],
                "close": [1],
                "volume": [1],
            }

            response = client.get("/market-data/NSE:RELIANCE?refresh=true")

            assert response.status_code == 200
            mock_load.assert_called_once_with(["NSE:RELIANCE"])
