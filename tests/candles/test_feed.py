"""Tests for the UpstoxFeed protobuf-based market data feed."""

import pytest
from unittest.mock import AsyncMock

from terminal.candles.feed import UpstoxFeed
from terminal.candles.proto import MarketDataFeed_pb2 as pb


@pytest.fixture
def feed():
    return UpstoxFeed(access_token="test-token")


def _build_feed_response(
    instrument_key: str,
    ohlc_items: list[dict],
    feed_type: int = pb.live_feed,
    is_index: bool = False,
) -> bytes:
    """Build a protobuf FeedResponse binary for testing."""
    response = pb.FeedResponse()
    response.type = feed_type

    feed_msg = pb.Feed()
    full_feed = pb.FullFeed()

    market_ohlc = pb.MarketOHLC()
    for item in ohlc_items:
        ohlc = market_ohlc.ohlc.add()
        ohlc.interval = item.get("interval", "1d")
        ohlc.open = item.get("open", 0)
        ohlc.high = item.get("high", 0)
        ohlc.low = item.get("low", 0)
        ohlc.close = item.get("close", 0)
        ohlc.vol = item.get("vol", 0)
        ohlc.ts = item.get("ts", 0)

    if is_index:
        index_ff = pb.IndexFullFeed()
        index_ff.marketOHLC.CopyFrom(market_ohlc)
        full_feed.indexFF.CopyFrom(index_ff)
    else:
        market_ff = pb.MarketFullFeed()
        market_ff.marketOHLC.CopyFrom(market_ohlc)
        full_feed.marketFF.CopyFrom(market_ff)

    feed_msg.fullFeed.CopyFrom(full_feed)
    response.feeds[instrument_key].CopyFrom(feed_msg)

    return response.SerializeToString()


# --- OHLC extraction tests ---


def test_extract_ohlc_from_market_feed(feed):
    """Test extracting OHLC from MarketFullFeed."""
    # Build a Feed message with marketFF
    feed_msg = pb.Feed()
    full_feed = pb.FullFeed()
    market_ff = pb.MarketFullFeed()
    ohlc = market_ff.marketOHLC.ohlc.add()
    ohlc.interval = "1d"
    ohlc.open = 100.0
    ohlc.high = 110.0
    ohlc.low = 90.0
    ohlc.close = 105.0
    ohlc.vol = 50000
    ohlc.ts = 1735689600000
    full_feed.marketFF.CopyFrom(market_ff)
    feed_msg.fullFeed.CopyFrom(full_feed)

    result = UpstoxFeed._extract_ohlc(feed_msg)

    assert len(result) == 1
    assert result[0]["interval"] == "1D"
    assert result[0]["open"] == 100.0
    assert result[0]["high"] == 110.0
    assert result[0]["low"] == 90.0
    assert result[0]["close"] == 105.0
    assert result[0]["volume"] == 50000
    assert "2025-01-01T00:00:00+00:00" in result[0]["timestamp"]


def test_extract_ohlc_from_index_feed(feed):
    """Test extracting OHLC from IndexFullFeed."""
    feed_msg = pb.Feed()
    full_feed = pb.FullFeed()
    index_ff = pb.IndexFullFeed()
    ohlc = index_ff.marketOHLC.ohlc.add()
    ohlc.interval = "1d"
    ohlc.open = 22000.0
    ohlc.high = 22500.0
    ohlc.low = 21800.0
    ohlc.close = 22300.0
    ohlc.vol = 0
    ohlc.ts = 1735689600000
    full_feed.indexFF.CopyFrom(index_ff)
    feed_msg.fullFeed.CopyFrom(full_feed)

    result = UpstoxFeed._extract_ohlc(feed_msg)

    assert len(result) == 1
    assert result[0]["open"] == 22000.0


def test_extract_ohlc_multiple_intervals(feed):
    """Test extracting multiple OHLC intervals."""
    feed_msg = pb.Feed()
    full_feed = pb.FullFeed()
    market_ff = pb.MarketFullFeed()

    for interval in ["1d", "1w", "1M"]:
        ohlc = market_ff.marketOHLC.ohlc.add()
        ohlc.interval = interval
        ohlc.open = 100.0
        ohlc.high = 110.0
        ohlc.low = 90.0
        ohlc.close = 105.0

    full_feed.marketFF.CopyFrom(market_ff)
    feed_msg.fullFeed.CopyFrom(full_feed)

    result = UpstoxFeed._extract_ohlc(feed_msg)
    assert len(result) == 3
    intervals = [r["interval"] for r in result]
    assert intervals == ["1D", "1W", "1M"]


def test_extract_ohlc_empty_feed(feed):
    """Test that feed without fullFeed returns empty."""
    feed_msg = pb.Feed()
    # Only LTPC, no fullFeed
    ltpc = pb.LTPC()
    ltpc.ltp = 100.0
    feed_msg.ltpc.CopyFrom(ltpc)

    result = UpstoxFeed._extract_ohlc(feed_msg)
    assert len(result) == 0


# --- Subscription management tests ---


def test_subscription_tracking(feed):
    """Test that subscriptions are tracked correctly."""
    assert len(feed._subscribed_keys) == 0
    feed._subscribed_keys.add("NSE_EQ|INE002A01018")
    assert "NSE_EQ|INE002A01018" in feed._subscribed_keys


# --- Callback dispatch tests ---


@pytest.mark.asyncio
async def test_handle_feed_response_dispatches_callbacks(feed):
    """Test that feed responses dispatch to registered callbacks."""
    callback = AsyncMock()
    feed.on_candle(callback)
    feed._subscribed_keys.add("NSE_EQ|INE002A01018")

    # Build a FeedResponse
    raw = _build_feed_response(
        "NSE_EQ|INE002A01018",
        [
            {
                "interval": "1d",
                "open": 100.0,
                "high": 110.0,
                "low": 90.0,
                "close": 105.0,
                "vol": 50000,
                "ts": 1735689600000,
            }
        ],
    )

    response = pb.FeedResponse()
    response.ParseFromString(raw)

    await feed._handle_feed_response(response)

    callback.assert_called_once()
    args = callback.call_args[0]
    assert args[0] == "NSE_EQ|INE002A01018"
    assert args[1]["interval"] == "1D"
    assert args[1]["open"] == 100.0


@pytest.mark.asyncio
async def test_handle_feed_response_filters_unsubscribed(feed):
    """Test that unsubscribed instruments are filtered out."""
    callback = AsyncMock()
    feed.on_candle(callback)
    # Don't subscribe to this key
    feed._subscribed_keys.add("BSE_EQ|OTHER")

    raw = _build_feed_response(
        "NSE_EQ|INE002A01018",
        [{"interval": "1d", "open": 100.0, "high": 110.0, "low": 90.0, "close": 105.0}],
    )

    response = pb.FeedResponse()
    response.ParseFromString(raw)

    await feed._handle_feed_response(response)

    callback.assert_not_called()


def test_on_candle_registers_callback(feed):
    """Test callback registration."""
    assert len(feed._callbacks) == 0
    feed.on_candle(AsyncMock())
    assert len(feed._callbacks) == 1


def test_extract_ohlc_ist_normalization(feed):
    """Test that IST midnight (18:30 UTC) is normalized to UTC midnight of correct day."""
    feed_msg = pb.Feed()
    full_feed = pb.FullFeed()
    market_ff = pb.MarketFullFeed()
    ohlc = market_ff.marketOHLC.ohlc.add()
    ohlc.interval = "1d"
    # 2025-01-01 18:30:00 UTC = 2025-01-02 00:00:00 IST
    ohlc.ts = 1735756200000

    full_feed.marketFF.CopyFrom(market_ff)
    feed_msg.fullFeed.CopyFrom(full_feed)

    result = UpstoxFeed._extract_ohlc(feed_msg)
    # Should be 2025-01-02 00:00:00 UTC
    assert result[0]["timestamp"] == "2025-01-02T00:00:00+00:00"


def test_extract_ohlc_intraday_ist_offset(feed):
    """Test that intraday timestamps are shifted to IST (+05:30)."""
    feed_msg = pb.Feed()
    full_feed = pb.FullFeed()
    market_ff = pb.MarketFullFeed()
    ohlc = market_ff.marketOHLC.ohlc.add()
    ohlc.interval = "1m"
    # 2025-01-01 09:15:00 UTC
    ohlc.ts = 1735722900000

    full_feed.marketFF.CopyFrom(market_ff)
    feed_msg.fullFeed.CopyFrom(full_feed)

    result = UpstoxFeed._extract_ohlc(feed_msg)
    # Should be 2025-01-01 14:45:00 IST (+05:30)
    assert "+05:30" in result[0]["timestamp"]
    assert "2025-01-01T14:45:00+05:30" == result[0]["timestamp"]
