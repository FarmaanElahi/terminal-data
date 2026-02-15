import pytest
import json
from unittest.mock import patch, MagicMock
from terminal.tradingview.scanner import TradingViewScanner


@pytest.mark.asyncio
async def test_fetch_ohlc_mock():
    scanner = TradingViewScanner()
    mock_resp = {
        "data": [
            {
                "s": "NSE:RELIANCE",
                "d": [1672531200, 2500.0, 2550.0, 2490.0, 2520.0, 1000000.0],
            }
        ]
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.json.return_value = mock_resp

        results = await scanner.fetch_ohlc(markets=["india"])
        assert len(results) == 1
        assert results[0]["ticker"] == "NSE:RELIANCE"
        assert results[0]["close"] == 2520.0
        assert results[0]["timestamp"] == 1672531200


@pytest.mark.asyncio
async def test_fetch_symbols_mock():
    scanner = TradingViewScanner()
    mock_resp = {
        "data": [
            {
                "s": "NSE:RELIANCE",
                "d": [
                    "Reliance Industries",
                    "logoid",
                    True,
                    "isin",
                    "NSE",
                    "IN",
                    "stock",
                    ["common"],
                    [],
                ],
            }
        ]
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.json.return_value = mock_resp

        results = await scanner.fetch_symbols(markets=["india"])
        assert len(results) == 1
        assert results[0]["ticker"] == "NSE:RELIANCE"
        assert results[0]["name"] == "Reliance Industries"
