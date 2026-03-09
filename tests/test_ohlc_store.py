import numpy as np
import time
import pandas as pd
from terminal.market_feed import OHLCStore


def test_ohlc_store_init():
    store = OHLCStore(capacity_per_symbol=100)
    assert store.capacity == 100
    assert store.get_data("AAPL") is None


def test_load_history():
    store = OHLCStore(capacity_per_symbol=100)
    # Create a DataFrame with history data
    now = int(time.time())
    timestamps = [now - (50 - i) * 86400 for i in range(50)]
    history = pd.DataFrame(
        {
            "open": [100.0] * 50,
            "high": [105.0] * 50,
            "low": [95.0] * 50,
            "close": [102.0] * 50,
            "volume": [1000.0] * 50,
        },
        index=pd.Index(timestamps, name="timestamp"),
    )

    store.load_history("AAPL", history)
    df = store.get_data("AAPL")
    assert len(df) == 50
    # Verify columns — should have exactly 5 columns, no aliases
    assert list(df.columns) == ["open", "high", "low", "close", "volume", "timestamp"]
    # Verify float32 dtype
    assert df["close"].dtype == np.float32


def test_add_realtime_update():
    store = OHLCStore(capacity_per_symbol=100)
    ts = int(time.time())
    candle1 = (ts, 100.0, 105.0, 95.0, 102.0, 1000.0)
    store.add_realtime("AAPL", candle1)

    candle1_updated = (ts, 100.0, 110.0, 95.0, 108.0, 1500.0)
    store.add_realtime("AAPL", candle1_updated)

    df = store.get_data("AAPL")
    assert len(df) == 1
    assert df.loc[np.int32(ts), "close"] == np.float32(108.0)


def test_add_realtime_new_candle():
    store = OHLCStore(capacity_per_symbol=100)
    ts = int(time.time())
    candle1 = (ts, 100.0, 105.0, 95.0, 102.0, 1000.0)
    store.add_realtime("AAPL", candle1)

    candle2 = (ts + 86400, 102.0, 108.0, 101.0, 105.0, 1200.0)
    store.add_realtime("AAPL", candle2)

    df = store.get_data("AAPL")
    assert len(df) == 2
    assert df.index[-1] == np.int32(ts + 86400)


def test_ring_buffer_capacity():
    """Test that the ring buffer correctly evicts old entries."""
    store = OHLCStore(capacity_per_symbol=5)
    ts = int(time.time())

    # Add 7 candles to a buffer of capacity 5
    for i in range(7):
        store.add_realtime("AAPL", (ts + i * 86400, 100.0, 105.0, 95.0, 102.0, 1000.0))

    df = store.get_data("AAPL")
    assert len(df) == 5
    # The first two should be evicted, so first timestamp should be ts + 2*86400
    assert df.index[0] == np.int32(ts + 2 * 86400)
    assert df.index[-1] == np.int32(ts + 6 * 86400)


def test_has_symbol():
    store = OHLCStore(capacity_per_symbol=100)
    assert not store.has_symbol("AAPL")

    store.add_realtime("AAPL", (int(time.time()), 100.0, 105.0, 95.0, 102.0, 1000.0))
    assert store.has_symbol("AAPL")


def test_get_all_data():
    store = OHLCStore(capacity_per_symbol=100)
    ts = int(time.time())
    store.add_realtime("AAPL", (ts, 100.0, 105.0, 95.0, 102.0, 1000.0))
    store.add_realtime("MSFT", (ts, 200.0, 210.0, 195.0, 205.0, 2000.0))

    all_data = store.get_all_data()
    assert "AAPL" in all_data
    assert "MSFT" in all_data
    assert len(all_data["AAPL"]) == 1
    assert len(all_data["MSFT"]) == 1
