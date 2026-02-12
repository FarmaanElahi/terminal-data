import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from terminal.symbols.tasks import sync_symbols
from fsspec.implementations.memory import MemoryFileSystem


@pytest.mark.asyncio
async def test_sync_symbols_success():
    mock_symbols = [
        {"ticker": "NSE:RELIANCE", "name": "RELIANCE INDUSTRIES LTD"},
        {"ticker": "NASDAQ:AAPL", "name": "APPLE INC"},
    ]

    # Mock TradingViewScreenerClient
    with patch("terminal.symbols.tasks.TradingViewScreenerClient") as MockClient:
        instance = MockClient.return_value
        instance.fetch_symbols = AsyncMock(return_value=mock_symbols)

        mfs = MemoryFileSystem()
        bucket = "test-bucket"

        # Test sync with explicit dependencies
        count = await sync_symbols(fs=mfs, bucket=bucket)

        assert count == 2
        instance.fetch_symbols.assert_called_once()
        assert mfs.exists(f"{bucket}/symbols/symbols.json")


@pytest.mark.asyncio
async def test_sync_symbols_no_bucket():
    """
    ValueError is raised by persist_symbols if bucket is empty.
    """
    mock_fs = MagicMock()
    with pytest.raises(ValueError, match="OCI_BUCKET environment variable is not set"):
        await sync_symbols(fs=mock_fs, bucket="")
