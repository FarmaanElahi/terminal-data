import pytest
import asyncio
import numpy as np
import time
from unittest.mock import AsyncMock, patch, MagicMock
from terminal.market_data import OHLCStore, MarketDataManager, TradingViewDataProvider
from terminal.market_data.types import CANDLE_DTYPE


class MockDataProvider(TradingViewDataProvider):
    def __init__(self):
        super().__init__(fs=MagicMock(), bucket="test", cache_dir="/tmp/test_cache")

    def get_history(self, symbol: str) -> np.ndarray:
        history = np.zeros(10, dtype=CANDLE_DTYPE)
        for i in range(10):
            history[i] = (
                int(time.time()) - (10 - i) * 86400,
                100.0,
                105.0,
                95.0,
                102.0,
                1000.0,
            )
        return history

    async def fetch_realtime(self, markets=None):
        return [
            {
                "ticker": "AAPL",
                "timestamp": int(time.time()),
                "open": 100.0,
                "high": 110.0,
                "low": 90.0,
                "close": 105.0,
                "volume": 5000.0,
            }
        ]


@pytest.mark.asyncio
async def test_manager_load_history():
    store = OHLCStore()
    provider = MockDataProvider()
    manager = MarketDataManager(store, provider)

    await manager.load_history(["AAPL"])
    data = store.get_data("AAPL")
    assert data is not None
    assert len(data) == 10


@pytest.mark.asyncio
async def test_manager_polling():
    store = OHLCStore()
    provider = MockDataProvider()
    manager = MarketDataManager(store, provider)

    # Run polling for a short time
    await manager.start_realtime_polling(interval=0.1)
    await asyncio.sleep(0.2)
    await manager.stop_realtime_polling()

    data = store.get_data("AAPL")
    assert data is not None
    assert len(data) >= 1
    assert data[-1]["close"] == 105.0


@pytest.mark.asyncio
async def test_manager_get_ohlcv():
    store = OHLCStore()
    provider = MockDataProvider()
    manager = MarketDataManager(store, provider)

    await manager.load_history(["AAPL"])
    ohlcv = manager.get_ohlcv("AAPL")

    assert ohlcv is not None
    assert isinstance(ohlcv["close"], np.ndarray)
    assert len(ohlcv["close"]) == 10
    assert ohlcv["close"].dtype == np.float64
    assert len(ohlcv["timestamp"]) == 10


@pytest.mark.asyncio
async def test_manager_get_ohlcv_series():
    store = OHLCStore()
    provider = MockDataProvider()
    manager = MarketDataManager(store, provider)

    await manager.load_history(["AAPL"])
    series = manager.get_ohlcv_series("AAPL")

    assert series is not None
    assert isinstance(series, list)
    assert len(series) == 10
    # Each item should be a list [t, o, h, l, c, v]
    assert len(series[0]) == 6
    assert isinstance(series[0][0], int)  # timestamp
    assert isinstance(series[0][1], float)  # open
