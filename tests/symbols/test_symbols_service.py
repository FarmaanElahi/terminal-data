import pandas as pd
import pytest
from unittest.mock import patch, AsyncMock
from terminal.symbols.service import get_all_symbols_external
from terminal.symbols import service as symbol_service


@pytest.mark.asyncio
async def test_get_all_symbols_external_success():
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
    with patch("terminal.symbols.service.TradingView") as MockClient:
        instance = MockClient.return_value
        instance.scanner.fetch_symbols = AsyncMock(return_value=mock_symbols)

        # Test sync with explicit dependencies
        symbols = await get_all_symbols_external()

        assert len(symbols) == 2
        instance.scanner.fetch_symbols.assert_called_once()


@pytest.mark.asyncio
async def test_all_ticker():
    mock_df = pd.DataFrame({"ticker": ["TICK1", "TICK2", "TICK1"]})
    mock_fs = AsyncMock()
    mock_settings = AsyncMock()

    with patch.object(symbol_service, "_symbols_df", mock_df):
        from terminal.symbols.service import all_ticker

        tickers = await all_ticker(mock_fs, mock_settings)
        assert tickers == ["TICK1", "TICK2"]
