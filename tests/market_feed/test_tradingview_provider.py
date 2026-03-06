import pytest
import pandas as pd

from unittest.mock import MagicMock, AsyncMock
from pathlib import Path
from terminal.market_feed.tradingview import TradingViewDataProvider


@pytest.fixture
def mock_fs():
    return MagicMock()


@pytest.fixture
def tv_provider(mock_fs, tmp_path):
    return TradingViewDataProvider(
        fs=mock_fs, bucket="test-bucket", cache_dir=str(tmp_path)
    )


@pytest.mark.asyncio
async def test_scanner_fetch_ohlcv_mock(tv_provider):
    """Test that scanner fetch_ohlcv is called correctly."""
    import time

    now = int(time.time())
    mock_result = {
        "NSE:RELIANCE": (now, 2800.0, 2850.0, 2780.0, 2820.0, 1000000.0),
        "NSE:TCS": (now, 3500.0, 3550.0, 3480.0, 3520.0, 500000.0),
    }

    tv_provider._scanner.fetch_ohlcv = AsyncMock(return_value=mock_result)

    result = await tv_provider._scanner.fetch_ohlcv()
    assert "NSE:RELIANCE" in result
    assert result["NSE:RELIANCE"][4] == 2820.0  # close price


def test_save_load_cache(tv_provider):
    # Create dummy data
    df = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2023-01-01")],
            "open": [100.0],
            "high": [105.0],
            "low": [95.0],
            "close": [102.0],
            "volume": [1000.0],
            "symbol": ["AAPL"],
        }
    )

    cache_file = Path(tv_provider.cache_file_local)
    df.to_parquet(cache_file, index=False)

    # Test get_history — now returns a DataFrame
    history = tv_provider.get_history("AAPL")
    assert history is not None
    assert len(history) == 1
    assert history["close"].iloc[0] == pytest.approx(102.0, rel=1e-3)
    # Timestamp should be int32 seconds
    expected_ts = int(pd.Timestamp("2023-01-01").timestamp())
    assert history.index[0] == expected_ts


@pytest.mark.asyncio
async def test_refresh_cache_flow(tv_provider, mock_fs):
    import time

    now = int(time.time())
    mock_result = {
        "AAPL": (now, 100.0, 105.0, 95.0, 102.0, 1000.0),
    }

    tv_provider._scanner.fetch_ohlcv = AsyncMock(return_value=mock_result)

    await tv_provider.refresh_cache(["AAPL"])

    # Verify local file exists
    assert Path(tv_provider.cache_file_local).exists()

    # Verify FS.put was called to OCI
    mock_fs.put.assert_called_once()
    assert "candles_tv.parquet" in mock_fs.put.call_args[0][1]


@pytest.mark.asyncio
async def test_stream_live_ohlcv_aggregates_per_day(tv_provider):
    import time
    from unittest.mock import patch

    now = int(time.time())
    day_start = now - (now % 86400)

    async def fake_stream_quotes(tickers, fields=None):
        yield {
            "NSE:RELIANCE": {
                "open_price": 100.0,
                "high_price": 108.0,
                "low_price": 95.0,
                "lp": 103.0,
                "volume": 1200.0,
                "lp_time": now,
            }
        }
        yield {
            "NSE:RELIANCE": {
                "open_price": 99.0,
                "high_price": 112.0,
                "low_price": 94.0,
                "lp": 106.0,
                "volume": 2000.0,
                "lp_time": now + 120,
            }
        }

    with patch("terminal.tradingview.streamer2.streamer.stream_quotes", fake_stream_quotes):
        updates = []
        async for symbol, candle in tv_provider.stream_live_ohlcv(["NSE:RELIANCE"]):
            updates.append((symbol, candle))
            if len(updates) >= 2:
                break

    assert len(updates) == 2
    assert updates[0][1][0] == day_start
    assert updates[0][1][1] == 100.0
    assert updates[1][1][0] == day_start
    assert updates[1][1][1] == 100.0  # open remains first
    assert updates[1][1][2] == 112.0  # high is tracked
    assert updates[1][1][3] == 94.0   # low is tracked
    assert updates[1][1][5] == 2000.0 # latest cumulative volume
