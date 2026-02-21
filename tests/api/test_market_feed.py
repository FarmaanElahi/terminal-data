import pytest
import numpy as np
from fastapi.testclient import TestClient
from terminal.main import api
from unittest.mock import patch

client = TestClient(api)


@pytest.fixture
def mock_ohlc_data():
    data = np.zeros(
        1,
        dtype=[
            ("timestamp", "int64"),
            ("open", "float64"),
            ("high", "float64"),
            ("low", "float64"),
            ("close", "float64"),
            ("volume", "float64"),
        ],
    )
    data[0] = (1672531200, 100.0, 110.0, 90.0, 105.0, 5000.0)
    return data


def test_get_ohlcv_success(mock_ohlc_data):
    with patch(
        "terminal.market_feed.manager.MarketDataManager.get_ohlcv_series"
    ) as mock_get:
        mock_get.return_value = mock_ohlc_data.tolist()

        response = client.get("/market-feeds/candles/NSE:RELIANCE")

        assert response.status_code == 200
        json_resp = response.json()
        assert "data" in json_resp
        data = json_resp["data"]
        assert isinstance(data, list)
        assert data[0] == [1672531200, 100.0, 110.0, 90.0, 105.0, 5000.0]


def test_get_ohlcv_not_found():
    with patch(
        "terminal.market_feed.manager.MarketDataManager.get_ohlcv_series"
    ) as mock_get:
        # First call returns None, then manager.load_history is called, then second get_ohlcv returns None
        mock_get.return_value = None

        with patch(
            "terminal.market_feed.manager.MarketDataManager.load_history"
        ) as mock_load:
            mock_load.return_value = None

            response = client.get("/market-feeds/candles/UNKNOWN")

            assert response.status_code == 404
            assert "No data found" in response.json()["detail"]


def test_get_ohlcv_refresh():
    with patch(
        "terminal.market_feed.manager.MarketDataManager.load_history"
    ) as mock_load:
        with patch(
            "terminal.market_feed.manager.MarketDataManager.get_ohlcv_series"
        ) as mock_get:
            mock_get.return_value = [[1, 1, 1, 1, 1, 1]]

            response = client.get("/market-feeds/candles/NSE:RELIANCE?refresh=true")

            assert response.status_code == 200
            mock_load.assert_called_once_with(["NSE:RELIANCE"])
