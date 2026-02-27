"""Tests for the CandleManager service."""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock

from terminal.candles.service import CandleManager, detect_market
from terminal.candles.models import Candle
from terminal.candles.provider import CandleProvider


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
    Candle(
        timestamp="2025-01-02T00:00:00+05:30",
        open=105.0,
        high=115.0,
        low=95.0,
        close=110.0,
        volume=60000,
        oi=0,
    ),
]


# --- detect_market tests ---


def test_detect_market_nse():
    assert detect_market("NSE:RELIANCE") == "india"


def test_detect_market_bse():
    assert detect_market("BSE:RELIANCE") == "india"


def test_detect_market_nasdaq():
    assert detect_market("NASDAQ:AAPL") == "america"


def test_detect_market_nyse():
    assert detect_market("NYSE:GS") == "america"


def test_detect_market_default():
    """Unknown exchange defaults to india."""
    assert detect_market("UNKNOWN:SYMBOL") == "india"


def test_detect_market_no_colon():
    """Ticker without colon defaults to india."""
    assert detect_market("RELIANCE") == "india"


# --- Provider registry tests ---


@pytest.fixture
def mock_india_provider():
    provider = MagicMock(spec=CandleProvider)
    provider.market = "india"
    provider.get_candles = AsyncMock(return_value=SAMPLE_CANDLES)
    provider.get_candle_feed_token = MagicMock(return_value="NSE_EQ|INE002A01018")
    provider.close = AsyncMock()
    return provider


@pytest.fixture
def manager(mock_india_provider):
    return CandleManager(providers={"india": mock_india_provider})


def test_get_provider_for_ticker(manager, mock_india_provider):
    assert manager.get_provider_for_ticker("NSE:RELIANCE") is mock_india_provider
    assert manager.get_provider_for_ticker("NASDAQ:AAPL") is None


def test_register_provider(manager):
    us_provider = MagicMock(spec=CandleProvider)
    us_provider.market = "america"
    manager.register_provider(us_provider)
    assert manager.get_provider_for_ticker("NASDAQ:AAPL") is us_provider


@pytest.mark.asyncio
async def test_get_candles_delegates_to_provider(manager, mock_india_provider):
    """Test that manager delegates get_candles to the correct provider."""
    candles = await manager.get_candles(
        ticker="NSE:RELIANCE",
        interval="1D",
        from_date=date(2025, 1, 1),
        to_date=date(2025, 1, 2),
    )

    assert candles == SAMPLE_CANDLES
    mock_india_provider.get_candles.assert_called_once_with(
        "NSE:RELIANCE",
        "1D",
        date(2025, 1, 1),
        date(2025, 1, 2),
    )


@pytest.mark.asyncio
async def test_get_candles_no_provider(manager):
    """Test that missing provider returns empty list."""
    candles = await manager.get_candles(
        ticker="NASDAQ:AAPL",
        interval="1D",
    )
    assert candles == []


@pytest.mark.asyncio
async def test_subscribe_maps_tokens(manager, mock_india_provider):
    """Now delegates to provider."""
    await manager.subscribe("NSE:RELIANCE")
    mock_india_provider.subscribe.assert_called_once_with("NSE:RELIANCE")


@pytest.mark.asyncio
async def test_unsubscribe_cleans_mappings(manager, mock_india_provider):
    """Now delegates to provider."""
    await manager.unsubscribe("NSE:RELIANCE")
    mock_india_provider.unsubscribe.assert_called_once_with("NSE:RELIANCE")


@pytest.mark.asyncio
async def test_close_cleans_up(manager, mock_india_provider):
    """Test that close properly cleans up all providers."""
    await manager.close()
    mock_india_provider.close.assert_called_once()
