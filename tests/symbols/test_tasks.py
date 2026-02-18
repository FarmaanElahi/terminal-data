import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from terminal.symbols.tasks import sync_symbols
from fsspec.implementations.memory import MemoryFileSystem


@pytest.mark.asyncio
async def test_sync_symbols_success():
    mock_symbols = [
        {
            "ticker": "NSE:RELIANCE",
            "name": "RELIANCE INDUSTRIES LTD",
            "indexes": [{"name": "NIFTY 50", "proname": "NSE:NIFTY"}],
            "typespecs": ["common"],
        },
        {
            "ticker": "NASDAQ:AAPL",
            "name": "APPLE INC",
            "indexes": [{"name": "NASDAQ 100", "proname": "NDX"}],
            "typespecs": ["common"],
        },
    ]

    # Mock TradingView
    with patch("terminal.symbols.tasks.TradingView") as MockClient:
        instance = MockClient.return_value
        instance.scanner.fetch_symbols = AsyncMock(return_value=mock_symbols)

        mfs = MemoryFileSystem()
        bucket = "test-bucket"

        # Test sync with explicit dependencies
        symbols = await sync_symbols(fs=mfs, bucket=bucket)

        assert len(symbols) == 2
        instance.scanner.fetch_symbols.assert_called_once()


@pytest.mark.asyncio
async def test_sync_symbols_no_bucket():
    """
    Bucket check logic is moved up to router or handled by providers.
    """
    mock_fs = MagicMock()
    symbols = await sync_symbols(fs=mock_fs, bucket="")
    assert isinstance(symbols, list)
