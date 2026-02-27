"""Tests for the Upstox V3 HTTP client."""

import pytest
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock

from terminal.candles.upstox import UpstoxClient


# Sample Upstox API response data
SAMPLE_CANDLE_RESPONSE = {
    "status": "success",
    "data": {
        "candles": [
            ["2025-01-02T00:00:00+05:30", 53.1, 53.95, 51.6, 52.05, 235519861, 0],
            ["2025-01-01T00:00:00+05:30", 50.35, 56.85, 49.35, 52.8, 1004998611, 0],
        ]
    },
}


EMPTY_RESPONSE = {
    "status": "success",
    "data": {"candles": []},
}


ERROR_RESPONSE = {
    "status": "error",
    "errors": [{"errorCode": "UDAPI100050", "message": "Invalid instrument key"}],
}

MOCK_SYMBOL = {"ticker": "NSE:RELIANCE", "isin": "INE002A01018"}


@pytest.fixture
def mock_feed():
    feed = MagicMock()
    feed.start = AsyncMock()
    feed.stop = AsyncMock()
    feed.subscribe = AsyncMock()
    feed.unsubscribe = AsyncMock()
    return feed


@pytest.fixture
def client(mock_feed):
    return UpstoxClient(timeout=5.0, feed=mock_feed)


@pytest.mark.asyncio
async def test_get_candles_historical_success(client):
    """Test successful historical candle fetch and parsing."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = SAMPLE_CANDLE_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch("terminal.candles.upstox.get_symbol", return_value=MOCK_SYMBOL):
        with patch.object(client, "_ensure_client") as mock_ensure:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_ensure.return_value = mock_http

            candles = await client.get_candles(
                ticker="NSE:RELIANCE",
                interval="1D",  # Daily — TradingView format
                from_date=date(2025, 1, 1),
                to_date=date(2025, 1, 2),
            )

    assert len(candles) == 2
    # Reversed to chronological order — oldest first
    assert candles[0].open == 50.35
    assert candles[1].open == 53.1

    # Verify the correct URL path was called
    mock_http.get.assert_called_once()
    call_path = mock_http.get.call_args[0][0]
    assert "NSE_EQ%7CINE002A01018" in call_path
    # V3 format: /days/1/{to}/{from}
    assert "/days/1/" in call_path


@pytest.mark.asyncio
async def test_get_candles_intraday_success(client):
    """Test successful intraday candle fetch for today."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = SAMPLE_CANDLE_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch("terminal.candles.upstox.get_symbol", return_value=MOCK_SYMBOL):
        with patch.object(client, "_ensure_client") as mock_ensure:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_ensure.return_value = mock_http

            candles = await client.get_candles(
                ticker="NSE:RELIANCE",
                interval="1",  # 1 minute — TradingView format
            )

    assert len(candles) >= 2
    # Verify intraday URL: /historical-candle/intraday/{key}/minutes/1
    call_path = mock_http.get.call_args[0][0]
    assert "intraday" in call_path
    assert "minutes/1" in call_path


@pytest.mark.asyncio
async def test_get_candles_empty_response(client):
    """Test handling of empty candle data (noData signal)."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = EMPTY_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch("terminal.candles.upstox.get_symbol", return_value=MOCK_SYMBOL):
        with patch.object(client, "_ensure_client") as mock_ensure:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_ensure.return_value = mock_http

            candles = await client.get_candles(
                ticker="NSE:RELIANCE",
                interval="1D",
            )

    assert candles == []


def test_parse_candles_format():
    """Test that candle parsing handles array format correctly."""
    raw = [
        ["2025-01-02T00:00:00+05:30", 100.0, 110.0, 90.0, 105.0, 50000, 1200],
        ["2025-01-02T09:15:00+05:30", 100.0, 110.0, 90.0, 105.0, 50000, 1200],
    ]
    candles = UpstoxClient._parse_candles(raw)

    assert len(candles) == 2
    # Upstox returns newest-first, so after reversal oldest is first
    # Both timestamps are preserved as-is from Upstox
    assert candles[0].timestamp == "2025-01-02T09:15:00+05:30"
    assert candles[1].timestamp == "2025-01-02T00:00:00+05:30"


@pytest.mark.asyncio
async def test_subscribe_success(client, mock_feed):
    """Test that subscribe resolves ticker and calls feed."""
    with patch("terminal.candles.upstox.get_symbol", return_value=MOCK_SYMBOL):
        await client.subscribe("NSE:RELIANCE")

    mock_feed.subscribe.assert_called_once_with(["NSE_EQ|INE002A01018"])
    assert client._ticker_map["NSE_EQ|INE002A01018"] == "NSE:RELIANCE"


@pytest.mark.asyncio
async def test_unsubscribe_success(client, mock_feed):
    """Test that unsubscribe cleans up mappings and calls feed."""
    token = "NSE_EQ|INE002A01018"
    client._ticker_map[token] = "NSE:RELIANCE"
    with patch("terminal.candles.upstox.get_symbol", return_value=MOCK_SYMBOL):
        await client.unsubscribe("NSE:RELIANCE")

    mock_feed.unsubscribe.assert_called_once_with([token])
    assert token not in client._ticker_map


@pytest.mark.asyncio
async def test_on_update_yields_mapped_ticker(client):
    """Test that feed updates are piped to the update queue with mapped ticker."""
    client._ticker_map["TOKEN"] = "NSE:RELIANCE"
    ohlc = {"open": 100.0, "high": 110.0}

    await client._on_feed_update("TOKEN", ohlc)

    async for update in client.on_update():
        assert update["ticker"] == "NSE:RELIANCE"
        assert update["open"] == 100.0
        break


@pytest.mark.asyncio
async def test_client_close(client, mock_feed):
    """Test that close properly cleans up the HTTP client and feed."""
    http_client = await client._ensure_client()
    assert http_client is not None
    assert not http_client.is_closed

    await client.close()
    assert client._client is None
    mock_feed.stop.assert_called_once()


@pytest.mark.asyncio
async def test_get_candles_historical_pagination(client):
    """Test that deep history requests are chunked into multiple API calls."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = SAMPLE_CANDLE_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch("terminal.candles.upstox.get_symbol", return_value=MOCK_SYMBOL):
        with patch.object(client, "_ensure_client") as mock_ensure:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_ensure.return_value = mock_http

            # 2 years of daily data → 2 chunks (each 365 days)
            candles = await client.get_candles(
                ticker="NSE:RELIANCE",
                interval="1D",
                from_date=date(2023, 1, 1),
                to_date=date(2024, 1, 15),
            )
            assert len(candles) >= 2

    # Should make 2+ requests (one per 365-day chunk)
    assert mock_http.get.call_count >= 2


@pytest.mark.asyncio
async def test_interval_5_minute(client):
    """Test that 5-minute resolution uses /minutes/5 URL."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = SAMPLE_CANDLE_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch("terminal.candles.upstox.get_symbol", return_value=MOCK_SYMBOL):
        with patch.object(client, "_ensure_client") as mock_ensure:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_ensure.return_value = mock_http

            await client.get_candles(
                ticker="NSE:RELIANCE",
                interval="5",  # 5 minutes — TradingView format
            )

    call_path = mock_http.get.call_args[0][0]
    assert "minutes/5" in call_path


@pytest.mark.asyncio
async def test_interval_1_hour_maps_to_hours(client):
    """Test that 60-minute resolution maps to /hours/1."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = SAMPLE_CANDLE_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch("terminal.candles.upstox.get_symbol", return_value=MOCK_SYMBOL):
        with patch.object(client, "_ensure_client") as mock_ensure:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_ensure.return_value = mock_http

            await client.get_candles(
                ticker="NSE:RELIANCE",
                interval="60",  # 60 minutes = 1 hour in TradingView
                from_date=date(2025, 1, 1),
                to_date=date(2025, 1, 10),
            )

    call_path = mock_http.get.call_args[0][0]
    assert "hours/1" in call_path
