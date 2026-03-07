"""Tests for ChartSession in the realtime module."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from terminal.candles.models import Candle
from terminal.candles.service import CandleManager
from terminal.realtime.chart import ChartSession
from terminal.realtime.models import (
    ChartParams,
    CreateChartRequest,
    ModifyChartRequest,
    ResolveSymbolRequest,
)


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

MOCK_SYMBOL_DATA = {
    "ticker": "NSE:RELIANCE",
    "name": "Reliance Industries",
    "isin": "INE002A01018",
    "logo": "reliance-logo",
}


@pytest.fixture
def mock_candle_manager():
    manager = MagicMock(spec=CandleManager)
    manager.get_candles = AsyncMock(return_value=SAMPLE_CANDLES)
    manager.subscribe = AsyncMock()
    manager.unsubscribe = AsyncMock()
    manager.on_candle_update = MagicMock()
    return manager


@pytest.fixture
def mock_realtime():
    rt = MagicMock()
    rt.send = AsyncMock()
    rt.send_error = AsyncMock()
    return rt


@pytest.fixture
def chart_session(mock_realtime, mock_candle_manager):
    return ChartSession(
        "chart-1",
        realtime=mock_realtime,
        candle_manager=mock_candle_manager,
    )


@pytest.mark.asyncio
async def test_resolve_symbol_sends_metadata(chart_session, mock_realtime):
    """Test that resolve_symbol emits symbol_resolved."""
    with patch(
        "terminal.realtime.chart.get_symbol",
        return_value=MOCK_SYMBOL_DATA,
    ):
        msg = ResolveSymbolRequest(
            m="resolve_symbol",
            p=("chart-1", "NSE:RELIANCE"),
        )
        await chart_session.handle(msg)

    # Should have sent symbol_resolved response
    assert mock_realtime.send.call_count == 1

    # Check symbol_resolved
    resolved_call = mock_realtime.send.call_args[0][0]
    assert resolved_call.m == "symbol_resolved"
    assert resolved_call.p[1].ticker == "NSE:RELIANCE"
    assert "reliance-logo" in resolved_call.p[1].logo_urls[0]


@pytest.mark.asyncio
async def test_create_chart_sends_series(chart_session, mock_realtime):
    """Test that create_chart with params fetches candles and emits chart_series."""
    msg = CreateChartRequest(
        m="create_chart",
        p=("chart-1", ChartParams(symbol="NSE:RELIANCE", interval="1d")),
    )
    await chart_session.handle(msg)

    # Should have sent chart_series response
    assert mock_realtime.send.call_count == 1

    # Check chart_series
    series_call = mock_realtime.send.call_args[0][0]
    assert series_call.m == "chart_series"
    assert series_call.p[1] == "NSE:RELIANCE"
    assert len(series_call.p[3]) == 2


@pytest.mark.asyncio
async def test_resolve_symbol_not_found(chart_session, mock_realtime):
    """Test error handling when symbol is not found."""
    with patch(
        "terminal.realtime.chart.get_symbol",
        return_value=None,
    ):
        msg = ResolveSymbolRequest(
            m="resolve_symbol",
            p=("chart-1", "NSE:UNKNOWN"),
        )
        await chart_session.handle(msg)

    mock_realtime.send_error.assert_called_once()
    assert "Symbol not found" in mock_realtime.send_error.call_args[0][0]


@pytest.mark.asyncio
async def test_modify_chart_reloads(chart_session, mock_realtime, mock_candle_manager):
    """Test that modify_chart re-fetches candles for the new params."""
    create_msg = CreateChartRequest(
        m="create_chart",
        p=("chart-1", ChartParams(symbol="NSE:RELIANCE", interval="1d")),
    )
    await chart_session.handle(create_msg)

    mock_realtime.send.reset_mock()
    modify_msg = ModifyChartRequest(
        m="modify_chart",
        p=("chart-1", ChartParams(symbol="NSE:RELIANCE", interval="1m")),
    )
    await chart_session.handle(modify_msg)

    # Should have sent only series (now that resolution is separate)
    assert mock_realtime.send.call_count == 1
    series_call = mock_realtime.send.call_args[0][0]
    assert series_call.p[2] == "1m"


@pytest.mark.asyncio
async def test_streaming_updates_filtered_by_interval(
    chart_session, mock_realtime, mock_candle_manager
):
    """Test that stream loop filters by both ticker AND interval."""

    async def mock_generator():
        updates = [
            # Correct ticker, wrong interval
            {
                "ticker": "NSE:RELIANCE",
                "interval": "1m",
                "timestamp": "2025-01-01T10:00:00Z",
                "open": 100.0,
                "high": 110.0,
                "low": 90.0,
                "close": 105.0,
                "volume": 1000,
            },
            # Correct ticker, correct interval
            {
                "ticker": "NSE:RELIANCE",
                "interval": "1d",
                "timestamp": "2025-01-01T00:00:00Z",
                "open": 200.0,
                "high": 210.0,
                "low": 190.0,
                "close": 205.0,
                "volume": 2000,
            },
        ]
        for u in updates:
            yield u

    mock_candle_manager.on_candle_update.return_value = mock_generator()

    # Start streaming for 1d
    await chart_session._start_streaming("NSE:RELIANCE", "1d")

    # Give it a small moment to process the async generator
    await asyncio.sleep(0.1)

    # Should only have sent ONE update (the 1d one)
    assert mock_realtime.send.call_count == 1
    update_call = mock_realtime.send.call_args[0][0]
    assert update_call.p[2].open == 200.0


def test_stop_chart_session(chart_session):
    chart_session.stop()
    assert len(chart_session._streaming_tasks) == 0


def test_chart_repr(chart_session):
    assert "chart-1" in repr(chart_session)
