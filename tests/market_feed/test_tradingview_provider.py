import pytest
import pandas as pd

from unittest.mock import MagicMock, patch, PropertyMock
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
async def test_streamer_stream_bars_mock(tv_provider):
    # Mock the internal streamer's stream_bars call
    mock_bars = {"AAPL": [[1672531200, 100.0, 105.0, 95.0, 102.0, 1000.0]]}

    async def mock_stream_bars(tickers, timeframe="1D"):
        yield mock_bars

    with patch.object(
        type(tv_provider._tv), "streamer", new_callable=PropertyMock
    ) as mock_streamer_prop:
        mock_streamer = MagicMock()
        mock_streamer.stream_bars.side_effect = mock_stream_bars
        mock_streamer_prop.return_value = mock_streamer

        async for bar_dict in tv_provider._tv.streamer.stream_bars(["AAPL"]):
            assert "AAPL" in bar_dict
            assert bar_dict["AAPL"][0][4] == 102.0


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

    # Test get_history
    history = tv_provider.get_history("AAPL")
    assert len(history) == 1
    assert history[0]["close"] == 102.0
    # Match the conversion: ns // 10**9
    expected_ts = pd.Timestamp("2023-01-01").value // 10**9
    assert history[0]["timestamp"] == expected_ts


@pytest.mark.asyncio
async def test_refresh_cache_flow(tv_provider, mock_fs):
    mock_bars = {"AAPL": [[1672531200, 100.0, 105.0, 95.0, 102.0, 1000.0]]}

    async def mock_stream_bars_iter(tickers, timeframe="1D"):
        yield mock_bars

    with patch.object(
        type(tv_provider._tv), "streamer", new_callable=PropertyMock
    ) as mock_streamer_prop:
        mock_streamer = MagicMock()
        mock_streamer.stream_bars.side_effect = mock_stream_bars_iter
        mock_streamer_prop.return_value = mock_streamer
        await tv_provider.refresh_cache(["AAPL"])

    # Verify local file exists
    assert Path(tv_provider.cache_file_local).exists()

    # Verify FS.put was called to OCI
    mock_fs.put.assert_called_once()
    assert "candles_tv.parquet" in mock_fs.put.call_args[0][1]
