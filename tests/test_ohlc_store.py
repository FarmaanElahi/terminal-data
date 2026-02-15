import numpy as np
import time
from terminal.market_data import OHLCStore
from terminal.market_data.types import CANDLE_DTYPE


def test_ohlc_store_init():
    store = OHLCStore(capacity_per_symbol=100)
    assert store.capacity == 100
    assert store.get_data("AAPL") is None


def test_load_history():
    store = OHLCStore(capacity_per_symbol=100)
    history = np.zeros(50, dtype=CANDLE_DTYPE)
    for i in range(50):
        history[i] = (
            int(time.time()) - (50 - i) * 86400,
            100.0,
            105.0,
            95.0,
            102.0,
            1000.0,
        )

    store.load_history("AAPL", history)
    data = store.get_data("AAPL")
    assert len(data) == 50
    assert np.array_equal(data["timestamp"], history["timestamp"])


def test_add_realtime_update():
    store = OHLCStore(capacity_per_symbol=100)
    ts = int(time.time())
    candle1 = (ts, 100.0, 105.0, 95.0, 102.0, 1000.0)
    store.add_realtime("AAPL", candle1)

    candle1_updated = (ts, 100.0, 110.0, 95.0, 108.0, 1500.0)
    store.add_realtime("AAPL", candle1_updated)

    data = store.get_data("AAPL")
    assert len(data) == 1
    assert data[0]["close"] == 108.0


def test_add_realtime_new_candle():
    store = OHLCStore(capacity_per_symbol=100)
    ts = int(time.time())
    candle1 = (ts, 100.0, 105.0, 95.0, 102.0, 1000.0)
    store.add_realtime("AAPL", candle1)

    candle2 = (ts + 86400, 102.0, 108.0, 101.0, 105.0, 1200.0)
    store.add_realtime("AAPL", candle2)

    data = store.get_data("AAPL")
    assert len(data) == 2
    assert data[-1]["timestamp"] == ts + 86400
