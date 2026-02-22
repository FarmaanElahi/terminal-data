import pytest
import asyncio
import numpy as np
import time
from unittest.mock import MagicMock, AsyncMock
from terminal.market_feed import OHLCStore, MarketDataManager, TradingViewDataProvider
from terminal.market_feed.models import CANDLE_DTYPE


class MockDataProvider(TradingViewDataProvider):
    def __init__(self):
        super().__init__(fs=MagicMock(), bucket="test", cache_dir="/tmp/test_cache")
        self._tv = MagicMock()
        self._tv.streamer = MagicMock()

        async def mock_stream_quotes(tickers, fields=None):
            await asyncio.sleep(0.05)
            yield {
                "AAPL": {
                    "open_time": int(time.time()),
                    "open_price": 100.0,
                    "high_price": 110.0,
                    "low_price": 90.0,
                    "lp": 105.0,
                    "volume": 5000.0,
                }
            }
            # Add a sleep to prevent infinite tight loop in test
            await asyncio.sleep(0.01)

        self._tv.streamer.stream_quotes.side_effect = mock_stream_quotes

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
        self._history_dict[symbol] = history
        return history

    def update_cache(self, df):
        pass


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
async def test_manager_streaming_and_pubsub():
    store = OHLCStore()
    provider = MockDataProvider()
    manager = MarketDataManager(store, provider)

    # Start streaming
    await manager.start_realtime_streaming(["AAPL"])

    # Subscribe to updates
    updates = []

    async def subscriber_task():
        async for update in manager.subscribe("AAPL"):
            updates.append(update)
            if len(updates) >= 1:
                break

    sub_task = asyncio.create_task(subscriber_task())

    # Wait a bit for stream to yield
    await asyncio.sleep(0.1)

    # Clean up
    await manager.stop_realtime_streaming()
    await sub_task

    data = store.get_data("AAPL")
    assert data is not None
    assert len(data) >= 1
    assert data.iloc[-1]["close"] == 105.0

    assert len(updates) >= 1
    assert updates[0]["symbol"] == "AAPL"
    assert updates[0]["candle"][4] == 105.0  # close price


@pytest.mark.asyncio
async def test_manager_get_ohlcv():
    store = OHLCStore()
    provider = MockDataProvider()
    manager = MarketDataManager(store, provider)

    await manager.load_history(["AAPL"])
    ohlcv = manager.get_ohlcv("AAPL")

    assert ohlcv is not None
    assert isinstance(ohlcv["close"].values, np.ndarray)
    assert len(ohlcv["close"]) == 10
    assert ohlcv["close"].dtype == np.float64
    assert len(ohlcv.index) == 10


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
    # Verify latest is first
    assert series[0][0] > series[-1][0]
    assert isinstance(series[0][0], (int, float))  # timestamp
    assert isinstance(series[0][1], float)  # open


def test_provider_get_all_tickers():
    provider = MockDataProvider()
    # MockDataProvider hardcodes history for AAPL, let's see what it returns
    tickers = provider.get_all_tickers()
    # It seems MockDataProvider doesn't actually populate _history_dict until get_history is called
    # and get_all_tickers calls load_cache which might be empty if no files exist.
    # But get_history for AAPL will populate it if we call it.
    provider.get_history("AAPL")
    tickers = provider.get_all_tickers()
    assert "AAPL" in tickers


@pytest.mark.asyncio
async def test_manager_start():
    store = OHLCStore()
    provider = MockDataProvider()
    # Mock get_all_tickers to return something
    provider.get_history("AAPL")
    manager = MarketDataManager(store, provider)

    # Mock load_history and start_realtime_streaming to avoid actual streaming logic
    manager.load_history = AsyncMock()
    manager.start_realtime_streaming = AsyncMock()
    # manager._start_periodic_cache_updater = MagicMock() # It's already synchronous

    await manager.start()

    manager.load_history.assert_called_once_with(["AAPL"])
    manager.start_realtime_streaming.assert_called_once_with(["AAPL"])
