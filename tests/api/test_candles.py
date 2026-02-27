"""API tests for the candles router."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

from terminal.candles.models import Candle
from terminal.candles.service import CandleManager
from terminal.dependencies import get_candle_manager
from terminal.main import api


SAMPLE_CANDLES = [
    Candle(
        timestamp="2025-01-01T00:00:00+05:30",
        open=100.0,
        high=110.0,
        low=90.0,
        close=105.0,
        volume=50000,
        oi=0,
    ),
]


def _make_mock_manager() -> CandleManager:
    manager = MagicMock(spec=CandleManager)
    manager.get_candles = AsyncMock(return_value=SAMPLE_CANDLES)
    return manager


# Override the FastAPI dependency
_mock_manager = _make_mock_manager()
api.dependency_overrides[get_candle_manager] = lambda: _mock_manager

client = TestClient(api)


@pytest.fixture(autouse=True)
def reset_mock_manager():
    """Reset the mock manager between tests."""
    _mock_manager.get_candles.reset_mock()
    _mock_manager.get_candles.return_value = SAMPLE_CANDLES
    yield


def test_get_historical_candles_success():
    """Test successful historical candles endpoint."""
    response = client.get(
        "/candles/NSE:RELIANCE/historical?interval=1d&from_date=2025-01-01&to_date=2025-01-02"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "NSE:RELIANCE"
    assert data["interval"] == "1d"
    assert len(data["candles"]) == 1

    _mock_manager.get_candles.assert_called_once()
    args = _mock_manager.get_candles.call_args[1]
    assert args["ticker"] == "NSE:RELIANCE"


def test_get_intraday_candles_success():
    """Test successful intraday candles endpoint."""
    response = client.get("/candles/NSE:RELIANCE/intraday?interval=1m")

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "NSE:RELIANCE"
    assert data["interval"] == "1m"

    _mock_manager.get_candles.assert_called_once()


def test_get_intraday_rejects_daily_interval():
    """Test that intraday endpoint rejects non-intraday intervals."""
    response = client.get("/candles/NSE:RELIANCE/intraday?interval=1d")

    assert response.status_code == 400
    assert "not an intraday interval" in response.json()["detail"]
