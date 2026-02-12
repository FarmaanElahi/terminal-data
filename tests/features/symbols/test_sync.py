import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from features.symbols.sync import sync_symbols


@pytest.mark.asyncio
async def test_sync_symbols_success():
    mock_symbols = [
        {"ticker": "NSE:RELIANCE", "name": "RELIANCE INDUSTRIES LTD"},
        {"ticker": "NASDAQ:AAPL", "name": "APPLE INC"},
    ]

    # Mock TradingViewScreenerClient
    # We patch it where it is imported in features.symbols.sync
    with patch("features.symbols.sync.TradingViewScreenerClient") as MockClient:
        instance = MockClient.return_value
        instance.fetch_symbols = AsyncMock(return_value=mock_symbols)

        # Mock get_fs and the filesystem
        with patch("features.symbols.sync.get_fs") as mock_get_fs:
            mock_fs = MagicMock()
            mock_get_fs.return_value = mock_fs

            # Mock the context manager returned by fs.open
            mock_file = MagicMock()
            mock_fs.open.return_value.__enter__.return_value = mock_file

            # Mock OCI_BUCKET environment variable
            with patch.dict("os.environ", {"OCI_BUCKET": "test-bucket"}):
                count = await sync_symbols()

                assert count == 2
                instance.fetch_symbols.assert_called_once()
                mock_fs.open.assert_called_once_with(
                    "test-bucket/symbols/symbols.json", "w"
                )

                # Verify that json.dump was called (it's called in sync_symbols)
                # We can't easily verify the exact call to json.dump without patching json,
                # but we can verify something was written to the file if we wanted more detail.


@pytest.mark.asyncio
async def test_sync_symbols_no_bucket():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(
            ValueError, match="OCI_BUCKET environment variable is not set"
        ):
            await sync_symbols()
