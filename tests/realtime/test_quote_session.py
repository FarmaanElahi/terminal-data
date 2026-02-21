import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from terminal.realtime.quote import QuoteSession
from terminal.realtime.models import (
    CreateQuoteSessionRequest,
    SubscribeSymbolsRequest,
    UnsubscribeSymbolsRequest,
    FullQuoteResponse,
    QuoteUpdateResponse,
    QuoteData,
    QuoteUpdateData,
)


@pytest.mark.asyncio
async def test_quote_session_initial_emit():
    # Setup mocks
    manager = MagicMock()
    realtime = AsyncMock()
    session_id = "test_session"
    symbol = "NSE:RELIANCE"
    candle = (1600000000, 100.0, 105.0, 95.0, 102.0, 1000.0)

    manager.get_ohlcv_series.return_value = [candle]

    # Mock manager.subscribe as an async generator
    async def mock_subscribe():
        yield {
            "symbol": symbol,
            "candle": (1600000001, 102.5, 103.0, 102.0, 102.8, 500.0),
        }
        await asyncio.sleep(0.02)
        yield {
            "symbol": symbol,
            "candle": (
                1600000002,
                102.5,
                103.0,
                102.0,
                102.9,
                500.0,
            ),  # only time and close change
        }
        await asyncio.sleep(0.02)

    manager.subscribe.return_value = mock_subscribe()

    session = QuoteSession(session_id, realtime=realtime, manager=manager)

    # Trigger create_quote_session
    msg = CreateQuoteSessionRequest(m="create_quote_session", p=(session_id, [symbol]))
    await session.handle(msg)

    # Verify initial emit
    manager.get_ohlcv_series.assert_called_with(symbol, limit=1)

    expected_full_dict = {
        "timestamp": 1600000000,
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 102.0,
        "volume": 1000.0,
    }

    realtime.send.assert_any_call(
        FullQuoteResponse(
            p=(session_id, symbol, QuoteData(**expected_full_dict)),
        )
    )

    # Wait for background task to pick up stream update
    await asyncio.sleep(0.05)

    # Verify stream update
    expected_diff_dict = {
        "timestamp": 1600000001,
        "open": 102.5,
        "high": 103.0,
        "low": 102.0,
        "close": 102.8,
        "volume": 500.0,
    }
    realtime.send.assert_any_call(
        QuoteUpdateResponse(
            p=(session_id, symbol, QuoteUpdateData(**expected_diff_dict)),
        )
    )

    expected_diff_dict_2 = {
        "timestamp": 1600000002,
        "close": 102.9,
    }
    realtime.send.assert_any_call(
        QuoteUpdateResponse(
            p=(session_id, symbol, QuoteUpdateData(**expected_diff_dict_2)),
        )
    )

    session.stop()


@pytest.mark.asyncio
async def test_quote_session_subscribe_unsubscribe():
    manager = MagicMock()
    realtime = AsyncMock()
    session_id = "test_session"

    manager.get_ohlcv_series.return_value = []

    async def mock_subscribe():
        if False:
            yield {}  # Make it an async generator

    manager.subscribe.return_value = mock_subscribe()

    session = QuoteSession(session_id, realtime=realtime, manager=manager)

    # Initial subscribe
    await session.handle(
        CreateQuoteSessionRequest(m="create_quote_session", p=(session_id, ["AAPL"]))
    )
    assert "AAPL" in session.subscribed_symbols

    # Subscribe more
    await session.handle(
        SubscribeSymbolsRequest(m="subscribe_symbols", p=(session_id, ["GOOG"]))
    )
    assert "AAPL" in session.subscribed_symbols
    assert "GOOG" in session.subscribed_symbols

    # Unsubscribe
    await session.handle(
        UnsubscribeSymbolsRequest(m="unsubscribe_symbols", p=(session_id, ["AAPL"]))
    )
    assert "AAPL" not in session.subscribed_symbols
    assert "GOOG" in session.subscribed_symbols

    session.stop()
