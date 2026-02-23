import pytest
import asyncio
import time
import pandas as pd
from unittest.mock import MagicMock, AsyncMock
from terminal.market_feed import OHLCStore, MarketDataManager, TradingViewDataProvider


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

    def get_history(self, symbol: str) -> pd.DataFrame | None:
        """Returns a DataFrame with 10 rows of mock OHLCV data."""
        now = int(time.time())
        timestamps = [now - (10 - i) * 86400 for i in range(10)]
        df = pd.DataFrame(
            {
                "open": [100.0] * 10,
                "high": [105.0] * 10,
                "low": [95.0] * 10,
                "close": [102.0] * 10,
                "volume": [1000.0] * 10,
            },
            index=pd.Index(timestamps, name="timestamp"),
        )
        # Also populate _history_dict for get_all_tickers
        self._history_dict[symbol] = df
        return df

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
    assert data.iloc[-1]["close"] == pytest.approx(105.0, rel=1e-3)

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
    assert len(ohlcv["close"]) == 10
    assert len(ohlcv.index) == 10
    # No alias columns
    assert "O" not in ohlcv.columns
    assert "C" not in ohlcv.columns


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


def test_provider_get_all_tickers():
    provider = MockDataProvider()
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

    await manager.start()

    manager.load_history.assert_called_once_with(["AAPL"])
    manager.start_realtime_streaming.assert_called_once_with(["AAPL"])


@pytest.mark.asyncio
async def test_manager_lazy_load():
    """Test that get_ohlcv lazy-loads from provider when symbol is not in store."""
    store = OHLCStore()
    provider = MockDataProvider()
    manager = MarketDataManager(store, provider)

    # Don't call load_history — should lazy-load
    ohlcv = manager.get_ohlcv("AAPL")
    assert ohlcv is not None
    assert len(ohlcv) == 10
    assert store.has_symbol("AAPL")
