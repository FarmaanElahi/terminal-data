import numpy as np
from terminal.market_data import OHLCStore, MockDataProvider


def test_ohlc_store_init():
    store = OHLCStore(capacity_per_symbol=100)
    assert store.capacity == 100
    assert store.get_data("AAPL") is None


def test_load_history():
    store = OHLCStore(capacity_per_symbol=100)
    provider = MockDataProvider()

    # Generate random history
    history = provider.get_history("AAPL", periods=50)

    store.load_history("AAPL", history)

    data = store.get_data("AAPL")
    assert len(data) == 50
    assert np.array_equal(data["timestamp"], history["timestamp"])


def test_load_history_overflow():
    capacity = 10
    store = OHLCStore(capacity_per_symbol=capacity)
    provider = MockDataProvider()

    history = provider.get_history("AAPL", periods=20)

    store.load_history("AAPL", history)

    data = store.get_data("AAPL")
    assert len(data) == capacity
    # Should contain the *last* 10 candles
    assert np.array_equal(data["timestamp"], history["timestamp"][-capacity:])


def test_add_realtime_update():
    store = OHLCStore(capacity_per_symbol=100)
    provider = MockDataProvider()

    # Initial load
    history = provider.get_history("AAPL", periods=10)
    store.load_history("AAPL", history)

    # Simulate update to the last candle
    last_candle = history[-1]
    updated_candle = last_candle.copy()
    updated_candle["close"] += 1.0
    updated_candle["volume"] += 100

    store.add_realtime("AAPL", updated_candle)

    data = store.get_data("AAPL")
    assert len(data) == 10
    assert data[-1]["close"] == updated_candle["close"]
    assert data[-1]["volume"] == updated_candle["volume"]


def test_add_realtime_new_candle():
    store = OHLCStore(capacity_per_symbol=100)
    provider = MockDataProvider()

    history = provider.get_history("AAPL", periods=10)
    store.load_history("AAPL", history)

    # New candle (next day)
    new_timestamp = history[-1]["timestamp"] + 86400
    new_candle = (new_timestamp, 150.0, 155.0, 149.0, 152.0, 5000.0)

    store.add_realtime("AAPL", new_candle)

    data = store.get_data("AAPL")
    assert len(data) == 11
    assert data[-1]["timestamp"] == new_timestamp


def test_multi_symbol_isolation():
    store = OHLCStore(capacity_per_symbol=100)
    provider = MockDataProvider()

    aapl_history = provider.get_history("AAPL", periods=10)
    goog_history = provider.get_history("GOOG", periods=15)

    store.load_history("AAPL", aapl_history)
    store.load_history("GOOG", goog_history)

    aapl_data = store.get_data("AAPL")
    goog_data = store.get_data("GOOG")

    assert len(aapl_data) == 10
    assert len(goog_data) == 15

    # Update AAPL, verify GOOG unchanged
    new_candle = (aapl_data[-1]["timestamp"] + 86400, 100, 110, 90, 105, 1000)
    store.add_realtime("AAPL", new_candle)

    assert len(store.get_data("AAPL")) == 11
    assert len(store.get_data("GOOG")) == 15
